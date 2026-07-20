# SQLite 重构方案（方案 B · 无自动迁移）

## 目标

将 `output.json` / `user_api.json` / `static.json` 三个 JSON 数据文件的读写替换为 SQLite 数据库 `mock.db`，取消 `api_cache.json` 派生缓存文件。

## 数据库设计

单文件 `data/mock.db`，两张表：

```sql
-- 抓包接口数据（合并 mitmproxy + user_api）
CREATE TABLE IF NOT EXISTS api_data (
  id          TEXT PRIMARY KEY,
  type        TEXT NOT NULL DEFAULT 'MITMPROXY',  -- MITMPROXY / USER
  url         TEXT NOT NULL DEFAULT '',
  method      TEXT NOT NULL DEFAULT 'GET',
  params      TEXT NOT NULL DEFAULT '{}',         -- json string
  response    TEXT NOT NULL DEFAULT '{}',         -- json string
  route       TEXT NOT NULL DEFAULT '',           -- 去域名后的路径（冗余，加速查询）
  params_md5  TEXT NOT NULL DEFAULT '',           -- md5(method+sorted_params)，加速匹配
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_api_match ON api_data(route, method, params_md5);
CREATE INDEX IF NOT EXISTS idx_api_type  ON api_data(type);

-- 静态资源抓包记录
CREATE TABLE IF NOT EXISTS static_data (
  url        TEXT PRIMARY KEY,
  type       TEXT NOT NULL DEFAULT 'MITMPROXY',
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

- WAL 模式：`PRAGMA journal_mode=WAL`
- `api_cache.json` 取消，mock 服务启动时查库构建内存映射

## 新增文件

### `lib/db_lib.py` — SQLite 数据访问层

核心类 `MockDB`：

| 方法 | 用途 | 替代原函数 |
|---|---|---|
| `upsert_api(record)` | 单条插入/更新 | `add_user_api_data` / `update_user_api_data` |
| `batch_upsert_api(records)` | 批量写入 | `save_response` (mitmproxy_lib) |
| `get_api_list(type=None, reverse=False)` | 查询列表 | `get_mitmproxy_api_data_list` / `get_user_api_data_list` / `get_mock_api_data_list` |
| `update_api(record)` | 按 id 更新 | `update_user_api_data` |
| `delete_api(api_id)` | 按 id 删除 | `delete_user_api_data` |
| `get_api_by_match(route, method, params_md5)` | 精确匹配 | mock_server 内存查找 |
| `batch_upsert_static(urls)` | 批量写静态资源 | `save_static` (mitmproxy_lib) |
| `get_static_list()` | 查静态资源列表 | `load_static_cache` |

入库时冗余字段预计算：

```python
route = remove_url_domain(url)
if method == 'GET':
    route = remove_url_query(route)
sort_params = JsonFormat.format_and_sort_json_string(params)
params_md5 = create_md5(method + sort_params)
```

## 改造文件清单

### 1. `config/work_file.py`
- 新增 `DB_FILE_NAME = 'mock.db'`，`DB_DATA_PATH = f'{DATA_DIR}/{DB_FILE_NAME}'`
- `WORK_FILE_DICT` 中移除 `MITMPROXY_DATA` / `USER_API_DATA` / `STATIC_DATA` / `API_CACHE_DATA` 四项
- 保留 `MITMPROXY_DATA_PATH` / `USER_API_DATA_PATH` / `STATIC_DATA_PATH` 常量（暂不删，避免其他地方引用报错）

### 2. `lib/work_file_lib.py`
- `create_work_files` 不再创建上述四个 JSON 文件
- 新增确保 `mock.db` 初始化的逻辑（通过 `MockDB` 实例化）

### 3. `module/request_catch.py`
- `__init__`：`self.save_path` / `self.static_save_path` → `self.db_path`，初始化 `self.mock_db = MockDB(self.db_path)`
- `self.response_cache_dict` / `self.static_cache_dict` → 保留为内存缓冲
- `load_history_cache` → 简化为 `self.mock_db` 初始化即可
- `done()` 中：
  - `save_response(...)` → `self.mock_db.batch_upsert_api(records)`
  - `save_static(...)` → `self.mock_db.batch_upsert_static(urls)`
- `SimpleFolderBackup` 的 `watch_backup_files` → `['/mock.db']`

### 4. `lib/mitmproxy_lib.py`
- `save_response_to_cache` → 保留，内存缓冲去重
- `save_static_to_cache` → 保留，内存缓冲
- `load_response_cache` → 废弃
- `save_response` → 废弃
- `save_static` → 废弃
- `load_static_cache` → 废弃
- 移除 `import pandas` 和 `from lib.app_lib import get_mitmproxy_api_data_list`

### 5. `lib/app_lib.py`
- `get_mitmproxy_api_data_list` → 内部改 `mock_db.get_api_list(type='MITMPROXY', reverse=reverse)`，签名不变
- `get_user_api_data_list` → `mock_db.get_api_list(type='USER', reverse=reverse)`
- `get_mock_api_data_list` → `mock_db.get_api_list(reverse=reverse)`
- `save_user_api_data_list` → 废弃
- `add_user_api_data` → `mock_db.upsert_api(record)`
- `update_user_api_data` → `mock_db.update_api(record)`
- `delete_user_api_data` → `mock_db.delete_api(api_id)`
- `fix_user_api_data` → `mock_db.get_api_list(type='USER')` → 逐条 `update_api`
- 移除 `import pandas`
- 函数签名保持不变，调用方无需改动

### 6. `module/mock_server.py`
- `self.api_cache_path` → 移除
- `create_api_dict` → 从 `MockDB` 查询构建内存映射：
  ```
  api_list = mock_db.get_api_list()
  for row in api_list:
    request_key = md5(row['route'] + row['method'])
    response_key = row['params_md5']
    api_dict[request_key][response_key] = json.loads(row['response'])
  ```
- `get_server_api_dict(read_cache)` → `read_cache=False` 时查库构建；`read_cache=True` 时用内存缓存
- 移除 `API_CACHE_DATA_PATH` 导入

### 7. `config/enum/MITMPROXY.py`
- `MITMPROXY_DATA_FIELDS` → 保留，字段补全逻辑仍可能用到

## 不变的部分

- `mitmproxy_data_edit_dialog.py` — 调用的函数签名不变
- `open_mitmproxy_preview_html` — 数据格式不变
- 前端 web 页面 — 无感
- `SimpleFolderBackup` 类本身 — 只改 `watch_backup_files` 传参

## 实施顺序

1. `lib/db_lib.py` — 新建数据访问层
2. `config/work_file.py` — 新增 DB 常量，调整 `WORK_FILE_DICT`
3. `lib/work_file_lib.py` — 调整文件初始化逻辑
4. `lib/app_lib.py` — CRUD 改为调 `MockDB`，移除 pandas
5. `lib/mitmproxy_lib.py` — 废弃写文件函数，保留内存缓冲
6. `module/request_catch.py` — 改用 `MockDB`
7. `module/mock_server.py` — 改用 `MockDB` 查询，取消 `api_cache.json`
