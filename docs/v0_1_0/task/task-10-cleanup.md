# 子任务 10 — 连带清理（含 JSON 文件项移除）

## 目标

清理重构后不再使用的 `MITMPROXY_DATA_FIELDS`、`fix_dict_field`、`pandas` 依赖，以及从 task-03 延后的 `WORK_FILE_DICT` JSON 文件项移除。

> **前置条件**：所有其他子任务（task-01 ~ task-09）均已完成。本任务移除的 JSON 文件项和导入语句在中间状态下仍被旧代码引用，提前移除会导致崩溃。

## 涉及文件

- `config/enum/MITMPROXY.py`
- `lib/utils_lib.py`
- `requirements.txt`
- `config/work_file.py`（从 task-03 延后）
- `lib/work_file_lib.py`（从 task-03 延后）

## `config/work_file.py`（从 task-03 延后）

- `WORK_FILE_DICT` 中移除 `MITMPROXY_DATA` / `USER_API_DATA` / `STATIC_DATA` / `API_CACHE_DATA` 四项
  > 此时 `app_lib.py` / `mitmproxy_lib.py` / `server_lib.py` / `request_catch.py` / `mock_server.py` 均已改为使用 `MockDB`，不再读写这些 JSON 文件，可安全移除。
- 保留 `MITMPROXY_DATA_PATH` / `USER_API_DATA_PATH` / `STATIC_DATA_PATH` 常量（暂不删，避免其他地方引用报错）
- 移除 `MITMPROXY_FILE_PATH` / `STATIC_FILE_NAME` / `API_CACHE_FILE_NAME` 三个"文件名"常量
  > `MITMPROXY_FILE_PATH` / `STATIC_FILE_NAME` 仅被 `request_catch.py` 的 `SimpleFolderBackup` 引用（task-06 已移除）；`API_CACHE_FILE_NAME` 仅用于构造 `API_CACHE_DATA_PATH`，而 `API_CACHE_DATA_PATH` 在本任务中已从 `WORK_FILE_DICT` 移除且 `mock_server.py` 不再引用（task-07 已移除），三者均无引用方，可安全删除

## `lib/work_file_lib.py`（从 task-03 延后）

- `create_work_files` 不再创建上述四个 JSON 文件
  > 此时所有进程均已改为首次 `MockDB` 实例化时自然创建 `mock.db`，不再依赖 `create_work_files` 创建 JSON 数据文件。

## `config/enum/MITMPROXY.py`

- `MITMPROXY_DATA_FIELDS` → **移除**
- 当前调用方共 3 处，重构后全部消失：
  - `lib/app_lib.py` 的 `get_mitmproxy_api_data_list` 中 `fix_dict_field(dict_data=..., fields=MITMPROXY_DATA_FIELDS)` → 重构后改用 `mock_db.get_api_list()`，DB schema 的 `NOT NULL DEFAULT` 已保证字段完整性，不再需要 `fix_dict_field` 补全
  - `lib/mitmproxy_lib.py` 的 `save_response` 中 `field_keys = [field.get('key') for field in MITMPROXY_DATA_FIELDS]` → 重构后 `save_response` 废弃
  - `lib/mitmproxy_lib.py` 顶部的 `from config.enum.MITMPROXY import MITMPROXY_DATA_FIELDS` → 随 `save_response` 废弃一并移除
- `MITMPROXY_DATA_FIELDS` 移除后，若文件中无其他内容则整个文件删除；`from lib.utils_lib import (generate_uuid, JsonFormat)` 导入也一并移除

## `lib/utils_lib.py`

- `fix_dict_field` 函数仅被 `app_lib.py` 的 `get_mitmproxy_api_data_list` 调用，重构后无调用方，一并移除

## `requirements.txt`

- 移除 `pandas==2.0.3`
- 原因：重构后 `lib/app_lib.py`、`lib/mitmproxy_lib.py`、`lib/server_lib.py` 三处 `import pandas` 全部移除，项目不再依赖 pandas（含其传递依赖 numpy），移除可减小打包体积
