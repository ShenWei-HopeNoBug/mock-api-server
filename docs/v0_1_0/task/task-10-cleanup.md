# 子任务 10 — 连带清理

## 目标

清理重构后不再使用的 `MITMPROXY_DATA_FIELDS`、`fix_dict_field` 以及 `pandas` 依赖。

## 涉及文件

- `config/enum/MITMPROXY.py`
- `lib/utils_lib.py`
- `requirements.txt`

## `config/enum/MITMPROXY.py`

- `MITMPROXY_DATA_FIELDS` → **移除**
- 当前调用方共 3 处，重构后全部消失：
  - `lib/app_lib.py` 的 `get_mitmproxy_api_data_list` 中 `fix_dict_field(dict_data=..., fields=MITMPROXY_DATA_FIELDS)` → 重构后改用 `mock_db.get_api_list()`，DB schema 的 `NOT NULL DEFAULT` 已保证字段完整性，不再需要 `fix_dict_field` 补全
  - `lib/mitmproxy_lib.py` 的 `save_response` 中 `field_keys = [field.get('key') for field in MITMPROXY_DATA_FIELDS]` → 重构后 `save_response` 废弃
  - `lib/mitmproxy_lib.py` 顶部的 `from config.enum.MITMPROXY import MITMPROXY_DATA_FIELDS` → 随 `save_response` 废弃一并移除
- `MITMPROXY_DATA_FIELDS` 移除后，若文件中无其他内容则整个文件删除；`from lib.utils_lib import (generate_uuid, JsonFormat)` 导入也一并移除

## `lib/utils_lib.py`

- `fix_dict_field` 函数仅被 `app_lib.py` 的 `get_mitmproxy_api_data_list` 调用，重构后无调用方，一并移除

## `lib/app_lib.py` 连带清理

- 移除 `from config.enum.MITMPROXY import MITMPROXY_DATA_FIELDS`
- 移除 `from lib.utils_lib import fix_dict_field`

## `requirements.txt`

- 移除 `pandas==2.0.3`
- 原因：重构后 `lib/app_lib.py`、`lib/mitmproxy_lib.py`、`lib/server_lib.py` 三处 `import pandas` 全部移除，项目不再依赖 pandas（含其传递依赖 numpy），移除可减小打包体积
