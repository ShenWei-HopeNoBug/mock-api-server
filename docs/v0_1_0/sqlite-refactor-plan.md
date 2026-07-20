# SQLite 重构方案（方案 B · 无自动迁移）

## 目标

将 `output.json` / `user_api.json` / `static.json` 三个 JSON 数据文件的读写替换为 SQLite 数据库 `mock.db`，取消 `api_cache.json` 派生缓存文件。

## 数据库设计

单文件 `data/mock.db`，两张表：

```sql
-- 抓包接口数据（合并 mitmproxy + user_api）
CREATE TABLE IF NOT EXISTS api_data (
  id             TEXT PRIMARY KEY,
  type           TEXT NOT NULL DEFAULT 'MITMPROXY',  -- MITMPROXY / USER
  url            TEXT NOT NULL DEFAULT '',
  method         TEXT NOT NULL DEFAULT 'GET',
  params         TEXT NOT NULL DEFAULT '{}',          -- 原始顺序 json string（展示 + SIMPLE_MATCH 匹配）
  params_sorted  TEXT NOT NULL DEFAULT '{}',          -- 排序后 json string（仅用于自然键去重）
  response       TEXT NOT NULL DEFAULT '{}',          -- json string
  route          TEXT NOT NULL DEFAULT '',            -- 去域名后的路径（冗余，加速查询）
  created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 自然键唯一索引：DB 层保证去重，(type, route, method, params_sorted) 相同则覆盖
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_natural ON api_data(type, route, method, params_sorted);
CREATE INDEX IF NOT EXISTS idx_api_route ON api_data(route, method);
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

### MockDB 连接 / 实例管理策略

项目实际为**多进程**模型，DB 访问分布在三个独立进程中：

| 进程 | DB 访问场景 | 线程模型 |
|---|---|---|
| 主进程（PyQt GUI） | UI 增删改、下载查列表、预览查列表 | PyQt 主线程 + 多个 `@create_thread` 线程，**并发读写** |
| mitmproxy 进程 | `done()` 批量写入 | 单线程，单次写入 |
| mock_server 进程 | `create_api_dict` 启动时查一次 | 单线程，启动后不再访问 DB |

**策略：进程级单例 + `check_same_thread=False` + 写锁**

1. **每个进程各自创建一个 `MockDB` 实例**（进程间内存隔离，天然独立连接）
2. 连接参数：`sqlite3.connect(db_path, check_same_thread=False)`，使同一进程内多线程可共享连接
3. **写操作加 `threading.Lock`**：主进程的 UI 线程和 `@create_thread` 线程可能并发写，锁保证串行化，避免 `sqlite3.ProgrammingError`
4. **`PRAGMA busy_timeout=5000`**：跨进程锁竞争时等待 5s 而非立即抛 `database is locked`
5. 读操作无需加锁（WAL 模式允许读写并发）

> **不采用"每线程独立连接"的原因**：本项目并发量极低（桌面 GUI），每线程独立连接会增加文件锁竞争和 `database is locked` 概率；进程级单例 + `check_same_thread=False` + 写锁已足够。
>
> **mock_server 进程特殊说明**：`create_api_dict` 仅启动时读一次 DB，之后 Flask 请求只查内存 `api_dict`，无运行时 DB 访问，无需考虑 Flask `threaded=True` 的多线程问题。

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
| `batch_upsert_static(urls)` | 批量写静态资源 | `save_static` (mitmproxy_lib) |
| `get_static_list()` | 查静态资源列表 | `load_static_cache` |

入库时冗余字段预计算及归一化：

```python
route = remove_url_domain(url)
if method == 'GET':
    route = remove_url_query(route)
# params 保持原始顺序（展示 + SIMPLE_MATCH 匹配）
params = JsonFormat.format_json_string(params)
# params_sorted 排序归一化，仅用于自然键去重
params_sorted = JsonFormat.format_and_sort_json_string(params)
```

> **`params` vs `params_sorted` 分离的原因**
>
> `SIMPLE_MATCH` 模式下 `mock_server` 构建内存映射时走 `format_json_string`（不排序），
> 请求侧同样不排序，两侧靠**原始顺序一致**来命中。
> 若 `params` 列本身排序存储，则存储侧永远是排序序，请求侧保持原始序，两侧不一致导致命中失败。
> 因此 `params` 列必须保留原始顺序，排序版本独立存 `params_sorted` 列仅供自然键去重使用。

> `params_md5` 不入库，由 `mock_server` 启动构建内存映射时根据当前 `http_params_match_mode` 实时计算，兼容 `EXACT_MATCH` 和 `SIMPLE_MATCH` 两种模式。

### 去重策略

`id` 保持主键，现有 UI 按 id 增删改零适配。通过自然键唯一索引 `idx_api_natural(type, route, method, params_sorted)` 在 DB 层保证去重。

两种写入场景使用不同冲突策略：

**mitmproxy 批量写入**（`batch_upsert_api`）— 自然键冲突时只更新 response：
```sql
INSERT INTO api_data (id, type, url, method, params, params_sorted, response, route)
VALUES (?, 'MITMPROXY', ?, ?, ?, ?, ?, ?)
ON CONFLICT(type, route, method, params_sorted) DO UPDATE SET
  response=excluded.response, url=excluded.url
```

**user 增/改**（`upsert_api`）— id 冲突或自然键冲突均替换：
```sql
INSERT OR REPLACE INTO api_data (id, type, url, method, params, params_sorted, response, route)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```
- id 冲突 → 替换同 id 记录（等价 update）
- 自然键冲突 → 删除旧记录插入新的（等价覆盖去重）
- 两者都冲突 → 替换

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
    request_key = self.__get_request_dict_key(row['route'], row['method'])
    params = self.__get_params_json_string(row['params'])
    response_key = self.__get_response_dict_key(row['method'], params)
    api_dict[request_key][response_key] = json.loads(row['response'])
  ```
  - `response_key` 通过现有 `__get_params_json_string` + `__get_response_dict_key` 实时计算，自动适配 `http_params_match_mode`
- `get_server_api_dict(read_cache)` → `read_cache=False` 时查库构建；`read_cache=True` 时用内存缓存
- 移除 `API_CACHE_DATA_PATH` 导入

### 7. `lib/server_lib.py`
- `get_static_data_list` → 内部改 `mock_db.get_static_list()`，签名不变
- 移除 `import pandas` 和 `from config.work_file import STATIC_DATA_PATH`
- 调用方 `lib/download_lib.py` 无需改动

### 8. `config/enum/MITMPROXY.py`
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
6. `lib/server_lib.py` — `get_static_data_list` 改用 `MockDB`，移除 pandas
7. `module/request_catch.py` — 改用 `MockDB`
8. `module/mock_server.py` — 改用 `MockDB` 查询，取消 `api_cache.json`
