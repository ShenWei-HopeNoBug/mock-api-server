# 子任务 05 — mitmproxy_lib 与 server_lib 改造

## 目标

废弃 `mitmproxy_lib.py` 中的 JSON 文件写入函数（保留内存缓冲去重函数），将 `server_lib.py` 的静态资源查询改为调用 `MockDB`。

> **前置依赖**：本任务必须在 task-06（request_catch 改造）完成后执行。`mitmproxy_lib` 中被废弃的 `save_response` / `save_static` / `load_response_cache` / `load_static_cache` 当前被 `request_catch.py` 调用，task-06 将 `request_catch` 改为使用 `MockDB` 后不再调用这些函数，才可安全删除。

## 涉及文件

- `lib/mitmproxy_lib.py`
- `lib/server_lib.py`

## `lib/mitmproxy_lib.py`

### 保留的函数

- `save_response_to_cache` → 保留，内存缓冲去重（task-06 的 `load_history_cache` 和 `done()` 仍需调用）
- `save_static_to_cache` → 保留，内存缓冲（同上）

### 废弃的函数（确认 task-06 完成后删除）

- `load_response_cache` → 废弃（原被 `request_catch.load_response_cache` 调用，task-06 已改为 `load_history_cache` 从 DB 加载）
- `save_response` → 废弃（原被 `request_catch.done()` 调用，task-06 已改为 `batch_upsert_api`）
- `save_static` → 废弃（原被 `request_catch.done()` 调用，task-06 已改为 `batch_upsert_static`）
- `load_static_cache` → 废弃（原被 `request_catch.load_static_cache` 调用，task-06 已改为从 DB 加载）

### 移除的导入

- 移除 `import pandas`
- 移除 `from lib.app_lib import get_mitmproxy_api_data_list`
- 移除 `from config.enum.MITMPROXY import MITMPROXY_DATA_FIELDS`

## `lib/server_lib.py`

- `get_static_data_list` → 内部通过 `app_lib._get_mock_db(work_dir)` 获取 `MockDB` 实例后调用 `mock_db.get_static_list()`，签名不变
  > 与 task-04 中 `app_lib.py` 的单例缓存复用同一连接，避免独立创建连接。详见 task-04「`server_lib.py` 中的 `get_static_data_list` 同理」。
- 新增 `from lib.app_lib import _get_mock_db` 导入
- 移除 `import pandas` 和 `from config.work_file import STATIC_DATA_PATH`
- 调用方 `lib/download_lib.py` 无需改动
