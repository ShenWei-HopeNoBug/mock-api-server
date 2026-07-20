# 子任务 03 — 工作目录配置调整

## 目标

调整工作目录配置，新增 DB 文件常量，移除 JSON 数据文件项，调整文件初始化逻辑不再创建/检查 `mock.db`。

## 涉及文件

- `config/work_file.py`
- `lib/work_file_lib.py`

## `config/work_file.py`

- 新增 `DB_FILE_NAME = 'mock.db'`，`DB_DATA_PATH = f'{DATA_DIR}/{DB_FILE_NAME}'`
- `WORK_FILE_DICT` 中移除 `MITMPROXY_DATA` / `USER_API_DATA` / `STATIC_DATA` / `API_CACHE_DATA` 四项
- 保留 `MITMPROXY_DATA_PATH` / `USER_API_DATA_PATH` / `STATIC_DATA_PATH` 常量（暂不删，避免其他地方引用报错）

## `lib/work_file_lib.py`

- `create_work_files` 不再创建上述四个 JSON 文件，**也不创建 `mock.db`**
- `check_work_files` **不检查 `mock.db`**，保持原有逻辑不变（仅检查 `WORK_DIR_DICT` 中的目录 + `WORK_FILE_DICT` 中的文件）
- `mock.db` 由首次 `MockDB` 实例化自然创建（`MockDB.__init__` 中 `CREATE TABLE IF NOT EXISTS` 保证建表幂等），`data/` 目录已由 `WORK_DIR_DICT` 中的 `DATA_DIR` 在 `create_work_files` 中创建，`MockDB` 实例化时目录已就绪

### `create_work_files` 不实例化 `MockDB` 的原因

`create_work_files` 被**三个进程**调用（`request_catch.py` 的 `init()`、`mock_server.py` 的 `init()`、`qt_win/app.py` 的 `check_and_create_work_files`）。若在此函数中实例化 `MockDB` 创建 `mock.db`，会产生一个**不被管理的临时连接**：

- 在 `request_catch.py` 中，`init()` 先调 `create_work_files`（创建连接 A），随后 `__init__` 又创建 `self.mock_db = MockDB(...)`（连接 B），连接 A 泄漏且无法被外部 `close()`
- 在 `mock_server.py` 中同理，`create_work_files` 创建的连接与后续 `app_lib._get_mock_db` 缓存的连接是不同实例，违反进程级单例策略
- 三个进程各自创建临时连接，增加跨进程文件锁竞争

改为仅确保 `data/` 目录存在（已由 `WORK_DIR_DICT` 的 `DATA_DIR` 项处理），让各进程首次 `MockDB` 实例化时自然建库，连接由进程级单例管理，无泄漏风险。

### `check_work_files` 不检查 `mock.db` 的原因

`mock.db` 的生命周期由 `MockDB` 自管理：`MockDB.__init__` 中 `CREATE TABLE IF NOT EXISTS` + `PRAGMA user_version` 保证建库幂等，文件不存在时自动创建，已存在时跳过建表。这与 JSON 配置文件不同——JSON 文件需要预置默认内容（`WORK_FILE_DICT` 的 `default` 字段），缺失时必须通过 `create_work_files` 写入；`mock.db` 不需要预置数据，空库即为合法初始状态。因此 `check_work_files` 不检查 `mock.db`：

- **首次运行**：`check_work_files` 检查目录和 JSON 配置文件不存在 → 返回 `False` → 弹窗 → 用户确认 → `create_work_files` 创建目录和 JSON 文件 → 后续首次 `MockDB` 实例化自动创建 `mock.db`
- **用户手动删除 `mock.db`**：`check_work_files` 返回 `True`（不检查 `mock.db`），不弹窗 → 后续首次 `MockDB` 实例化自动重建 `mock.db`（空库），数据从备份恢复或重新抓包
- **用户删除 `data/` 目录**：`check_work_files` 返回 `False`（`DATA_DIR` 不存在）→ 弹窗 → `create_work_files` 重建 `data/` 目录 → 后续 `MockDB` 实例化创建 `mock.db`
