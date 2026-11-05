# 子任务 01 — 数据库设计与连接管理策略

## 目标

定义 `data/mock.db` 的表结构、WAL 模式、checkpoint 策略以及多进程连接管理策略，为后续 `MockDB` 实现提供设计基础。

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

-- schema 版本标记
PRAGMA user_version = 1;
```

### `created_at` / `updated_at` 使用毫秒精度的原因

`datetime('now','localtime')` 精度仅到秒，批量写入时多条记录可能取到相同时间戳，导致 UI 列表顺序抖动。
改用 `strftime('%Y-%m-%d %H:%M:%f','now','localtime')` 将精度提升到毫秒（`%f` 输出 `SSS` 毫秒部分），输出格式如 `2024-01-15 14:30:22.123`，
大幅降低同时间戳碰撞概率。不使用 `datetime('now','localtime','subsec')` 的原因：`subsec` 修饰符需 SQLite ≥ 3.43.0（2023-08），
本项目运行环境为 Python 3.8，其捆绑的 SQLite 版本通常 < 3.43，`strftime` 的 `%f` 格式符在所有 SQLite 3.x 版本中均支持，兼容性更好。
毫秒精度仍非绝对唯一，排序 tiebreaker（`id DESC`）保留不变。

### `static_data` 表 `updated_at` 列的原因

`static_data` 以 `url` 为 PRIMARY KEY，重复抓取同一 URL 时若用 `INSERT OR REPLACE` 会删除旧行再插入新行，
`created_at` 被重置为当前时间，导致该 URL 在列表中"跳到最新"。改用 `ON CONFLICT(url) DO UPDATE SET updated_at=...`
显式保留原 `created_at`，仅刷新 `updated_at`，保证列表顺序稳定。`get_static_list` 按 `created_at DESC, url DESC`
排序，追加 `url` 作为 tiebreaker 避免同毫秒记录顺序抖动（与 `api_data` 排序稳定性策略一致）。

## WAL 模式与 checkpoint 策略

- WAL 模式：`PRAGMA journal_mode=WAL`
- `api_cache.json` 取消，mock 服务启动时查库构建内存映射
- **WAL checkpoint 与 `-wal` 文件增长控制**：
  - `mock_server` 进程：`create_api_dict` 查完数据后**立即 `close()` 连接**，连接关闭时 SQLite 自动执行 checkpoint 将 `-wal` 合并回主库，该进程后续不再访问 DB，不会残留 `-wal` 文件
  - `mitmproxy` 进程：`done()` 批量写入完成后 `close()` 连接，同理触发自动 checkpoint
  - 主进程（PyQt GUI）：连接为进程级单例，生命周期与 GUI 一致，长期存活。在 `MockDB` 中**仅在批量写入操作（`batch_upsert_api` / `batch_upsert_static`）后**执行 `PRAGMA wal_checkpoint(PASSIVE)`，被动尝试将 `-wal` 合并回主库（不阻塞读写）；单条写入（`upsert_api` / `update_api` / `delete_api`）跳过 checkpoint，避免连续增删改时产生不必要的 I/O 开销；应用退出时 `close()` 触发最终 checkpoint
  - 综上，只有主进程连接长期存活，但通过批量写入后 `PASSIVE` checkpoint + 退出时 `close()` 可控制 `-wal` 文件增长在合理范围内
  - **异常退出时 WAL 残留处理**：
    - 上述 checkpoint 策略覆盖的是**正常退出**流程，进程被 kill / 崩溃 / 断电时 `close()` 不会执行，`-wal` / `-shm` 侧车文件会残留在磁盘上
    - SQLite 下次打开 DB 时能自动恢复（`-wal` 中已提交的事务会重放回主库，未提交的回滚），数据不会丢失，但 `-wal` 文件不会被主动合并/截断
    - 若 `mock_server` 子进程在主进程崩溃后仍存活并持有只读连接，`-wal` 无法被 checkpoint，可能持续增长
    - **对策**：`MockDB.__init__` 中设置 WAL 模式后，立即执行一次 `PRAGMA wal_checkpoint(TRUNCATE)` 强制将 `-wal` 合并回主库并截断文件，确保每次进程启动时自动清理上次异常退出可能残留的 `-wal`
    - `TRUNCATE` 模式在合并完成后将 `-wal` 文件截断为 0 字节（而非仅重置读指针），彻底回收磁盘空间

## 连接 / 实例管理策略

项目实际为**多进程**模型，DB 访问分布在三个独立进程中：

| 进程 | DB 访问场景 | 线程模型 |
|---|---|---|
| 主进程（PyQt GUI） | UI 增删改、下载查列表、预览查列表 | PyQt 主线程 + 多个 `@create_thread` 线程，**并发读写** |
| mitmproxy 进程 | `done()` 批量写入 | 单线程，单次写入 |
| mock_server 进程 | `create_api_dict` 启动时查一次 | 单线程，启动后不再访问 DB |

**策略：进程级单例 + `check_same_thread=False` + 读写共锁**

1. **每个进程各自创建一个 `MockDB` 实例**（进程间内存隔离，天然独立连接）
2. 连接参数：`sqlite3.connect(db_path, check_same_thread=False)`，使同一进程内多线程可共享连接
3. **`conn.isolation_level = None`（autocommit 模式）**：Python `sqlite3` 模块默认 `isolation_level` 为 `""`，会在执行 DML（INSERT/UPDATE/DELETE）前**自动开启隐式事务**。若代码中再显式 `execute('BEGIN TRANSACTION')`，会触发 `sqlite3.OperationalError: cannot start a transaction within a transaction`。设置 `isolation_level = None` 关闭隐式事务后，所有事务由代码显式 `BEGIN` / `COMMIT` / `ROLLBACK` 控制，与下方所有事务代码示例配合
4. **所有 DB 操作（读 + 写）共用同一把 `threading.Lock`**：主进程的 UI 线程和 `@create_thread` 线程可能并发访问 DB，锁保证串行化
5. **`PRAGMA busy_timeout=5000`**：跨进程锁竞争时等待 5s 而非立即抛 `database is locked`
6. WAL 模式允许读写并发，但仅限 SQLite 引擎层；Python `sqlite3.Connection` 对象本身**不是线程安全的**，`check_same_thread=False` 仅允许跨线程使用同一连接，不代表可以**并发**使用——两个线程同时在同一 connection 上 `execute()` 仍会触发 `sqlite3.ProgrammingError`，因此读操作也必须加锁

### 不采用"每线程独立连接"的原因

本项目并发量极低（桌面 GUI），每线程独立连接会增加文件锁竞争和 `database is locked` 概率；进程级单例 + `check_same_thread=False` + 读写共锁已足够，全局锁的性能影响可忽略。

### `isolation_level = None` 的必要性

Python `sqlite3` 默认 `isolation_level` 为 `""`（非 `None`），行为是：在第一条 DML 语句前自动 `BEGIN`，需要显式 `conn.commit()` 才会 `COMMIT`。此模式下**不能**再手动 `execute('BEGIN TRANSACTION')`，否则报 `cannot start a transaction within a transaction`。本项目所有写操作均采用显式 `BEGIN TRANSACTION` + `COMMIT` / `ROLLBACK` 的事务控制模式（见下方所有事务代码示例），因此**必须**设置 `isolation_level = None` 进入 autocommit 模式，将事务控制权完全交给应用代码。

### mock_server 进程特殊说明

`create_api_dict` 仅启动时读一次 DB，之后 Flask 请求只查内存 `api_dict`，无运行时 DB 访问，无需考虑 Flask `threaded=True` 的多线程问题。**读取完成后立即 `close()` 连接**，既释放文件锁，又触发 SQLite 自动 checkpoint 合并 `-wal` 文件，避免该进程退出后残留 `-wal`。

`mock_server` 进程通过 `app_lib.get_mock_api_data_list(work_dir=self.work_dir)` 间接调用 `app_lib._get_mock_db(work_dir)` 获取缓存的 `MockDB` 实例，因此 `close()` 也需通过 `app_lib` 暴露的接口完成。在 `app_lib.py` 中新增 `_close_mock_db(work_dir)` 函数，从 `_mock_db_cache` 中取出实例并 `close()`，同时从缓存中移除。`create_api_dict` 在遍历完 `mock_api_data_list` 后、写入 `api_dict` 完成前调用 `app_lib._close_mock_db(self.work_dir)`，确保连接在进程退出前已关闭，不依赖进程终止时的隐式清理。

### mitmproxy 进程特殊说明

`done()` 批量写入完成后同样 `close()` 连接，触发自动 checkpoint。两个子进程均为"用完即关"，运行期间只有主进程持有长期连接。

### 主进程 MockDB 实例获取方式

`app_lib.py` 中的 `get_mitmproxy_api_data_list` / `get_user_api_data_list` / `get_mock_api_data_list` / `add_user_api_data` / `update_user_api_data` / `delete_user_api_data` 等函数签名保持不变（均接收 `work_dir` 参数），函数内部需要获取 `MockDB` 实例来执行 DB 操作。采用**模块级懒加载单例**：在 `app_lib.py` 模块级维护一个 `_mock_db_cache: dict`，以 `work_dir` 的**绝对路径**为 key 缓存 `MockDB` 实例，首次调用时创建，后续复用。这样同一 `work_dir` 下所有函数共享同一个 `MockDB` 连接（即同一个进程级单例），与上方"进程级单例"策略一致；`download_lib.py` / `server_lib.py` 等通过 `app_lib.py` 函数间接访问 DB 的调用方无需感知 `MockDB` 的存在。`request_catch.py` / `mock_server.py` 等子进程各自直接实例化 `MockDB`，不经过此缓存。

### 主进程连接退出时关闭

主进程的 `MockDB` 连接为长期存活的单例，需在应用退出时显式 `close()` 以触发最终 checkpoint。在 `app_lib.py` 中新增 `close_all_mock_db()` 函数，遍历 `_mock_db_cache` 中所有实例执行 `close()` 并清空缓存。`qt_win/app.py` 的 `closeEvent` 中在用户确认退出后、设置 `client_exit` 全局变量前调用 `close_all_mock_db()`，确保 `-wal` 文件在进程退出前被合并回主库。

## Schema 版本管理

建表后执行 `PRAGMA user_version = 1` 标记当前 schema 版本。`MockDB.__init__` 中建表完成后读取 `PRAGMA user_version`，与代码中定义的 `CURRENT_SCHEMA_VERSION` 比对：

- `user_version == 0`：全新数据库（`CREATE TABLE IF NOT EXISTS` 刚建完），直接写入 `CURRENT_SCHEMA_VERSION`
- `user_version == CURRENT_SCHEMA_VERSION`：版本匹配，无需处理
- `user_version < CURRENT_SCHEMA_VERSION`：旧版数据库，未来在此分支中执行增量迁移（`ALTER TABLE` / `CREATE INDEX` 等），当前版本仅 v1，无迁移逻辑
- `user_version > CURRENT_SCHEMA_VERSION`：数据库版本比代码新（用户降级运行旧版程序），给出警告日志但不阻断启动，避免数据被旧代码意外破坏

选择 `PRAGMA user_version` 而非 meta 表的原因：`user_version` 是 SQLite 内置机制，存储在数据库文件头中，不占额外表，读写零成本，且不受 `CREATE TABLE IF NOT EXISTS` 的幂等性影响——即使表已存在，`user_version` 仍能区分是旧库还是新库。
