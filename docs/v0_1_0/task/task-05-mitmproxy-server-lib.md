# 子任务 05 — mitmproxy_lib 与 server_lib 改造

## 目标

废弃 `mitmproxy_lib.py` 中的 JSON 文件写入函数（保留内存缓冲去重函数），将 `server_lib.py` 的静态资源查询改为调用 `MockDB`。

## 涉及文件

- `lib/mitmproxy_lib.py`
- `lib/server_lib.py`

## `lib/mitmproxy_lib.py`

### 保留的函数

- `save_response_to_cache` → 保留，内存缓冲去重
- `save_static_to_cache` → 保留，内存缓冲

### 废弃的函数

- `load_response_cache` → 废弃
- `save_response` → 废弃
- `save_static` → 废弃
- `load_static_cache` → 废弃

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
