# SQLite 重构方案（无自动迁移）

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
  response       TEXT NOT NULL DEFAULT '{}',          -- json string
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_api_type ON api_data(type);

-- 静态资源抓包记录
CREATE TABLE IF NOT EXISTS static_data (
  url         TEXT PRIMARY KEY,
  type        TEXT NOT NULL DEFAULT 'MITMPROXY',
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);
```

> **`created_at` / `updated_at` 使用毫秒精度的原因**
>
> `datetime('now','localtime')` 精度仅到秒，批量写入时多条记录可能取到相同时间戳，导致 UI 列表顺序抖动。
> 改用 `strftime('%Y-%m-%d %H:%M:%f','now','localtime')` 将精度提升到毫秒（`%f` 输出 `SSS` 毫秒部分），输出格式如 `2024-01-15 14:30:22.123`，
> 大幅降低同时间戳碰撞概率。不使用 `datetime('now','localtime','subsec')` 的原因：`subsec` 修饰符需 SQLite ≥ 3.43.0（2023-08），
> 本项目运行环境为 Python 3.8，其捆绑的 SQLite 版本通常 < 3.43，`strftime` 的 `%f` 格式符在所有 SQLite 3.x 版本中均支持，兼容性更好。
> 毫秒精度仍非绝对唯一，排序 tiebreaker（`id DESC`）保留不变。

> **`static_data` 表 `updated_at` 列的原因**
>
> `static_data` 以 `url` 为 PRIMARY KEY，重复抓取同一 URL 时若用 `INSERT OR REPLACE` 会删除旧行再插入新行，
> `created_at` 被重置为当前时间，导致该 URL 在列表中"跳到最新"。改用 `ON CONFLICT(url) DO UPDATE SET updated_at=...`
> 显式保留原 `created_at`，仅刷新 `updated_at`，保证列表顺序稳定。`get_static_list` 按 `created_at DESC, url DESC`
> 排序，追加 `url` 作为 tiebreaker 避免同毫秒记录顺序抖动（与 `api_data` 排序稳定性策略一致）。

- WAL 模式：`PRAGMA journal_mode=WAL`
- `api_cache.json` 取消，mock 服务启动时查库构建内存映射
- **WAL checkpoint 与 `-wal` 文件增长控制**：
  - `mock_server` 进程：`create_api_dict` 查完数据后**立即 `close()` 连接**，连接关闭时 SQLite 自动执行 checkpoint 将 `-wal` 合并回主库，该进程后续不再访问 DB，不会残留 `-wal` 文件
  - `mitmproxy` 进程：`done()` 批量写入完成后 `close()` 连接，同理触发自动 checkpoint
  - 主进程（PyQt GUI）：连接为进程级单例，生命周期与 GUI 一致，长期存活。在 `MockDB` 中于每次写入操作后执行 `PRAGMA wal_checkpoint(PASSIVE)`，被动尝试将 `-wal` 合并回主库（不阻塞读写）；应用退出时 `close()` 触发最终 checkpoint
  - 综上，只有主进程连接长期存活，但通过写入后 `PASSIVE` checkpoint + 退出时 `close()` 可控制 `-wal` 文件增长在合理范围内
  - **异常退出时 WAL 残留处理**：
    - 上述 checkpoint 策略覆盖的是**正常退出**流程，进程被 kill / 崩溃 / 断电时 `close()` 不会执行，`-wal` / `-shm` 侧车文件会残留在磁盘上
    - SQLite 下次打开 DB 时能自动恢复（`-wal` 中已提交的事务会重放回主库，未提交的回滚），数据不会丢失，但 `-wal` 文件不会被主动合并/截断
    - 若 `mock_server` 子进程在主进程崩溃后仍存活并持有只读连接，`-wal` 无法被 checkpoint，可能持续增长
    - **对策**：`MockDB.__init__` 中设置 WAL 模式后，立即执行一次 `PRAGMA wal_checkpoint(TRUNCATE)` 强制将 `-wal` 合并回主库并截断文件，确保每次进程启动时自动清理上次异常退出可能残留的 `-wal`
    - `TRUNCATE` 模式在合并完成后将 `-wal` 文件截断为 0 字节（而非仅重置读指针），彻底回收磁盘空间

### MockDB 连接 / 实例管理策略

项目实际为**多进程**模型，DB 访问分布在三个独立进程中：

| 进程 | DB 访问场景 | 线程模型 |
|---|---|---|
| 主进程（PyQt GUI） | UI 增删改、下载查列表、预览查列表 | PyQt 主线程 + 多个 `@create_thread` 线程，**并发读写** |
| mitmproxy 进程 | `done()` 批量写入 | 单线程，单次写入 |
| mock_server 进程 | `create_api_dict` 启动时查一次 | 单线程，启动后不再访问 DB |

**策略：进程级单例 + `check_same_thread=False` + 读写共锁**

1. **每个进程各自创建一个 `MockDB` 实例**（进程间内存隔离，天然独立连接）
2. 连接参数：`sqlite3.connect(db_path, check_same_thread=False)`，使同一进程内多线程可共享连接
3. **所有 DB 操作（读 + 写）共用同一把 `threading.Lock`**：主进程的 UI 线程和 `@create_thread` 线程可能并发访问 DB，锁保证串行化
4. **`PRAGMA busy_timeout=5000`**：跨进程锁竞争时等待 5s 而非立即抛 `database is locked`
5. WAL 模式允许读写并发，但仅限 SQLite 引擎层；Python `sqlite3.Connection` 对象本身**不是线程安全的**，`check_same_thread=False` 仅允许跨线程使用同一连接，不代表可以**并发**使用——两个线程同时在同一 connection 上 `execute()` 仍会触发 `sqlite3.ProgrammingError`，因此读操作也必须加锁

> **不采用"每线程独立连接"的原因**：本项目并发量极低（桌面 GUI），每线程独立连接会增加文件锁竞争和 `database is locked` 概率；进程级单例 + `check_same_thread=False` + 读写共锁已足够，全局锁的性能影响可忽略。
>
> **mock_server 进程特殊说明**：`create_api_dict` 仅启动时读一次 DB，之后 Flask 请求只查内存 `api_dict`，无运行时 DB 访问，无需考虑 Flask `threaded=True` 的多线程问题。**读取完成后立即 `close()` 连接**，既释放文件锁，又触发 SQLite 自动 checkpoint 合并 `-wal` 文件，避免该进程退出后残留 `-wal`。
>
> **mitmproxy 进程特殊说明**：`done()` 批量写入完成后同样 `close()` 连接，触发自动 checkpoint。两个子进程均为"用完即关"，运行期间只有主进程持有长期连接。

## 新增文件

### `lib/db_lib.py` — SQLite 数据访问层

核心类 `MockDB`：

| 方法 | 用途 | id 来源 | 替代原函数 |
|---|---|---|---|
| `upsert_api(record)` → `id` | 新增插入（纯 INSERT，不去重），返回生成的 id | MockDB 内部 `generate_uuid()` | `add_user_api_data` |
| `batch_upsert_api(records)` | 批量写入（应用层去重后纯 INSERT） | record 中已有（mitmproxy 抓包时生成） | `save_response` (mitmproxy_lib) |
| `get_api_list(type=None, reverse=False)` | 查询列表（默认 `ORDER BY created_at DESC, id DESC`，`reverse=True` 时改为 `ASC, id ASC`） | — | `get_mitmproxy_api_data_list` / `get_user_api_data_list` |
| `update_api(record)` | 按 id 更新（`UPDATE ... WHERE id = ?`） | 调用方传入 | `update_user_api_data` |
| `delete_api(api_id)` | 按 id 删除 | 调用方传入 | `delete_user_api_data` |
| `batch_upsert_static(urls)` | 批量写静态资源（`ON CONFLICT(url) DO UPDATE SET updated_at`，重复抓取刷新更新时间） | — | `save_static` (mitmproxy_lib) |
| `get_static_list()` | 查静态资源列表（`ORDER BY created_at DESC, url DESC`） | — | `load_static_cache` |

> **`batch_upsert_static` 同样采用单事务 + `executemany`**
>
> 与 `batch_upsert_api` 策略一致，将所有静态资源记录包裹在一个事务中批量执行：
> ```sql
> INSERT INTO static_data (url, type) VALUES (?, 'MITMPROXY')
> ON CONFLICT(url) DO UPDATE SET updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
> ```
> ```python
> with self._lock:
>   conn = self._conn
>   conn.execute('BEGIN TRANSACTION')
>   try:
>     conn.executemany(sql, records)
>     conn.execute('COMMIT')
>   except Exception:
>     conn.execute('ROLLBACK')
>     raise
>   finally:
>     self._wal_checkpoint_passive()
> ```
> - 单事务保证原子性，避免部分写入的中间状态
> - `executemany` 批量执行，缩短跨进程锁竞争窗口
> - commit 后执行 `PRAGMA wal_checkpoint(PASSIVE)` 合并 `-wal`

> **`get_api_list` 返回格式**
>
> 返回 `list[dict]`，每个 dict 包含 DB 中 `api_data` 表的**所有字段**：
> ```python
> {
>   'id': str,
>   'type': str,           # MITMPROXY / USER
>   'url': str,
>   'method': str,
>   'params': str,         # 原始顺序 json string
>   'response': str,       # json string
>   'created_at': str,     # 创建时间
>   'updated_at': str,     # 更新时间
> }
> ```
> SQL：`SELECT id, type, url, method, params, response, created_at, updated_at FROM api_data WHERE type=? ORDER BY created_at DESC, id DESC`
>
> **排序稳定性说明**：`created_at` 精度到毫秒（`strftime('%Y-%m-%d %H:%M:%f','now','localtime')`），大幅降低批量写入时多条记录取到相同 `created_at` 值的概率。但毫秒仍非绝对唯一——高并发或批量 `executemany` 极快写入时仍可能碰撞，因此追加 `id DESC` 作为 tiebreaker，`id` 为 UUID 全局唯一，保证相同 `created_at` 的行有确定的排列顺序。`reverse=True` 时改为 `ORDER BY created_at ASC, id ASC`，保持双向排序的对称性。
> 相比原 JSON 数据格式新增了 `created_at` / `updated_at` 两个字段。
> 前端 / 预览页面只取 `id` / `type` / `url` / `method` / `params` / `response`，多出的字段不影响渲染。
> `mock_server.create_api_dict` 始终从 `url` 实时计算 `route`（`remove_url_domain` + `remove_url_query`），不依赖 DB 冗余字段。

> **id 生成职责下沉到 MockDB**
>
> `upsert_api`（新增场景）由 MockDB 内部调用 `generate_uuid()` 生成 id，调用方无需传 id，
> 避免前端传入原记录 id 导致复制操作变成更新原记录。
> `update_api`（编辑场景）由调用方传入 id 定位记录。
> `batch_upsert_api`（抓包场景）record 中的 id 由 `request_catch.py` 在 `response()` 阶段已生成。

入库时字段归一化：

```python
# params 保持原始顺序（展示 + SIMPLE_MATCH 匹配）
params = JsonFormat.format_json_string(params)
```

> **`params` 不排序存储的原因**
>
> `SIMPLE_MATCH` 模式下 `mock_server` 构建内存映射时走 `format_json_string`（不排序），
> 请求侧同样不排序，两侧靠**原始顺序一致**来命中。
> 若 `params` 列排序存储，则存储侧永远是排序序，请求侧保持原始序，两侧不一致导致命中失败。

> `params_md5` 不入库，由 `mock_server` 启动构建内存映射时根据当前 `http_params_match_mode` 实时计算，兼容 `EXACT_MATCH` 和 `SIMPLE_MATCH` 两种模式。

### 去重策略

DB 层不做去重，`id` 为唯一主键，去重全部在**应用层**处理。三种写入场景均为纯 INSERT 或 UPDATE，不依赖自然键唯一索引。

**mitmproxy 批量写入**（`batch_upsert_api`）— 应用层去重后纯 INSERT：
```sql
INSERT INTO api_data (id, type, url, method, params, response)
VALUES (?, 'MITMPROXY', ?, ?, ?, ?)
```
> 去重逻辑保留在 `mitmproxy_lib.save_response_to_cache` 的内存缓冲阶段（与当前行为一致），`done()` 时将去重后的 records 批量写入 DB。

> **批量写入采用单事务 + `executemany`**
>
> `batch_upsert_api` 将所有记录包裹在**一个事务**中，使用 `executemany` 批量执行：
> ```python
> with self._lock:
>   conn = self._conn
>   conn.execute('BEGIN TRANSACTION')
>   try:
>     conn.executemany(sql, records)
>     conn.execute('COMMIT')
>   except Exception:
>     conn.execute('ROLLBACK')
>     raise
>   finally:
>     self._wal_checkpoint_passive()
> ```
> - 整个批量只获取/释放一次 SQLite 文件写锁，commit 时间从 O(n) 次降为 O(1) 次，大幅缩短跨进程锁竞争窗口
> - 事务保证原子性：要么全部写入成功，要么全部回滚，不会出现部分写入的中间状态
> - WAL 模式下读写不互斥，批量写入期间主进程仍可正常读操作，仅在 `COMMIT` 的短暂瞬间有文件锁竞争
> - commit 后执行 `PRAGMA wal_checkpoint(PASSIVE)` 合并 `-wal`（见上文 checkpoint 策略）

**user 新增/复制**（`upsert_api`）— id 由 MockDB 内部生成，纯 INSERT：
```sql
INSERT INTO api_data (id, type, url, method, params, response)
VALUES (?, ?, ?, ?, ?, ?)
```
- 每次调用均插入新记录，不去重，复制操作正常产生新记录

> id 由 MockDB 内部 `generate_uuid()` 生成，新增场景永远不会有 id 冲突。

**user 编辑**（`update_api`）— 按 id 定位 UPDATE，无冲突处理：
```sql
UPDATE api_data SET
  type=?, url=?, method=?, params=?, response=?,
  updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
WHERE id=?
```
```python
def update_api(self, record):
  with self._lock:
    conn = self._conn
    conn.execute('BEGIN TRANSACTION')
    try:
      conn.execute(update_sql, params)
      conn.execute('COMMIT')
    except Exception:
      conn.execute('ROLLBACK')
      raise
    finally:
      self._wal_checkpoint_passive()
```

> **`update_api` 无需冲突处理的原因**
>
> DB 层无自然键唯一索引，按 id 更新不会触发 `IntegrityError`，无需 delete + retry 逻辑。

> **`created_at` vs `updated_at` 分离的原因**
>
> 新增 `updated_at` 列记录实际修改时间。`get_api_list` 按 `created_at` 排序保证展示顺序稳定。

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
- **移除所有 `SimpleFolderBackup` 相关代码**：
  - 移除 `from lib.backup_lib import SimpleFolderBackup` 导入
  - 移除 `__init__` 中 `self.simple_folder_backup` 实例创建及 `source_dir` / `backup_dir` 相关变量
  - 移除 `init()` 中 `self.simple_folder_backup.watch_diff_backup()` 调用
  - 移除 `done()` 中 `self.simple_folder_backup.watch_diff_backup()` 调用
  - 原因：WAL 模式下 `copytree` 复制 `mock.db` + `-wal` + `-shm` 侧车文件无法保证一致性，后续单独用 SQLite 原生 `backup()` API 或 `VACUUM INTO` 实现一致性快照

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
- `get_mock_api_data_list` → 保持两次查询合并，与当前行为一致：
  ```python
  api_list = mock_db.get_api_list(type='MITMPROXY', reverse=reverse)
  api_list.extend(mock_db.get_api_list(type='USER', reverse=reverse))
  return api_list
  ```
  > **不改为单次 `get_api_list()` 查询的原因**：当前实现 `mitmproxy_list.extend(user_list)` 使 USER 数据在后，`create_api_dict` 遍历时后写入覆盖先写入，即 USER 永远优先于 MITMPROXY。若改为单次 `ORDER BY created_at` 查询，同路由记录的覆盖优先级由 `created_at` 决定而非 type，会导致用户手动编辑的 USER 数据被旧的 MITMPROXY 数据覆盖。两次查询合并保持原有优先级语义，零回归风险。
- `save_user_api_data_list` → 废弃
- `add_user_api_data` → 构造 record（不含 id）→ `mock_db.upsert_api(record)`，id 由 MockDB 内部生成
- `update_user_api_data` → 构造 record（含 id）→ `mock_db.update_api(record)`
- `delete_user_api_data` → `mock_db.delete_api(api_id)`
- `fix_user_api_data` → 改为 no-op 直接返回 `True`（SQLite schema 的 `NOT NULL DEFAULT` + `PRIMARY KEY` 已保证数据完整性，不存在字段缺失/id 缺失问题；保留函数签名避免前端 `fix_mock_data` 事件调用报错，后续前端移除按钮时再一并清理）
- 移除 `import pandas`
- 函数签名保持不变，调用方无需改动

### 6. `module/mock_server.py`
- `self.api_cache_path` → 移除
- `create_api_dict` → 从 `MockDB` 查询构建内存映射（保留静态资源链接替换逻辑，仅移除 `api_cache.json` 写入）：
  ```python
  assets_reg = get_static_match_regexp(self.include_files)
  assets_route = STATIC_DELAY_ROUTE if self.static_load_speed > 0 else self.static_url_path
  assets_base_url = '{}{}'.format(self.static_host, assets_route)

  def assets_replace_method(match):
    assets_url = match[0]
    file_name = assets_url.split('/')[-1]
    return '{}/{}'.format(assets_base_url, file_name)

  api_dict = {}
  mock_api_data_list = get_mock_api_data_list(work_dir=self.work_dir)
  for row_data in mock_api_data_list:
    response = row_data.get('response')
    method = row_data.get('method')
    params = row_data.get('params')
    # 始终从 url 实时计算 route
    route = remove_url_domain(row_data.get('url', ''))
    if method == 'GET':
      route = remove_url_query(route)

    request_key = self.__get_request_dict_key(route, method)
    response_key = self.__get_response_dict_key(method, self.__get_params_json_string(params))

    if request_key not in api_dict:
      api_dict[request_key] = {}
    # 替换静态资源链接
    if len(self.include_files):
      response = assets_reg.sub(assets_replace_method, response)
    api_dict[request_key][response_key] = json.loads(response)
  ```
  - `response_key` 通过现有 `__get_params_json_string` + `__get_response_dict_key` 实时计算，自动适配 `http_params_match_mode`
  - `route` 始终从 `url` 实时计算（`remove_url_domain` + `remove_url_query`）
  - 移除 `api_cache.json` 文件写入（`with open(self.api_cache_path, ...) → fl.write(...)`）
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
- `SimpleFolderBackup` 类本身 — 保留，本次不调用（自动备份移除，后续适配 SQLite 后再启用）

## 实施顺序

1. `lib/db_lib.py` — 新建数据访问层
2. `config/work_file.py` — 新增 DB 常量，调整 `WORK_FILE_DICT`
3. `lib/work_file_lib.py` — 调整文件初始化逻辑
4. `lib/app_lib.py` — CRUD 改为调 `MockDB`，移除 pandas
5. `lib/mitmproxy_lib.py` — 废弃写文件函数，保留内存缓冲
6. `lib/server_lib.py` — `get_static_data_list` 改用 `MockDB`，移除 pandas
7. `module/request_catch.py` — 改用 `MockDB`
8. `module/mock_server.py` — 改用 `MockDB` 查询，取消 `api_cache.json`
