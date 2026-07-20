# 子任务 07 — mock_server 改造

## 目标

将 `module/mock_server.py` 的 `create_api_dict` 从读 `api_cache.json` 改为从 `MockDB` 查询构建内存映射，移除缓存模式相关逻辑。

## 涉及文件

- `module/mock_server.py`
- `qt_ui/main_win/win_ui.ui`（可选 — 移除 `cacheCheckBox` UI 元素）

## 新增导入

```python
from lib.app_lib import _close_mock_db
```

> `_close_mock_db` 用于 `create_api_dict` 读取完成后关闭 DB 连接，详见 task-04。

## `create_api_dict` 改造

从 `MockDB` 查询构建内存映射（保留静态资源链接替换逻辑，仅移除 `api_cache.json` 写入）：

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

### 读取完成后关闭 DB 连接

`create_api_dict` 在遍历完 `mock_api_data_list` 后调用 `app_lib._close_mock_db(self.work_dir)`，关闭并移除 `_mock_db_cache` 中的实例。`close()` 触发 SQLite 自动 checkpoint，将 `-wal` 合并回主库，避免该进程退出后残留 `-wal` 文件。关闭连接放在数据遍历完成之后、`api_dict` 构建完成之前，确保 DB 读取已全部结束：

```python
api_dict = {}
mock_api_data_list = get_mock_api_data_list(work_dir=self.work_dir)
# 查询完毕，关闭 DB 连接（触发 checkpoint，释放文件锁）
_close_mock_db(work_dir=self.work_dir)
for row_data in mock_api_data_list:
  ...
```

> `qt_ui/main_win/win_ui.ui` 中 `cacheCheckBox` 的移除为可选项，保留也不影响功能（仅不再绑定逻辑）。若移除，需同步检查 `.ui` 文件对应的 `win_ui.py` 是否有自动生成的引用需要清理。

> **关闭时机在遍历前而非遍历后**：`get_mock_api_data_list` 返回的是 `list`（已在内存中），`_close_mock_db` 后遍历 `mock_api_data_list` 不再访问 DB，数据完整无影响。将 `close()` 提前到遍历前而非 `create_api_dict` 末尾，可更早释放文件锁，减少与其他进程的锁竞争窗口。

## 移除缓存模式

- `self.api_cache_path` → 移除
- `get_server_api_dict(read_cache)` → **整个方法移除**，`start_server` 直接调用 `create_api_dict()`
- `start_server(self, read_cache=False)` → 移除 `read_cache` 参数，签名改为 `start_server(self)`
- 移除 `API_CACHE_DATA_PATH` 导入

### 移除 `read_cache` / 缓存模式的原因

原 `read_cache=True` 路径依赖 `api_cache.json` 文件，重构后该文件取消。DB 查询构建 `api_dict` 的耗时与读缓存文件相当（单次 `SELECT` + 内存遍历），无需保留缓存模式。
移除范围包括：

- `module/mock_server.py`：`get_server_api_dict` 方法整体删除，`start_server` 去掉 `read_cache` 参数
- `qt_win/app.py`：移除 `self.cache` 属性、`cache_checkbox_click` 回调、`cacheCheckBox` 信号绑定与禁用控制、`server_config` 中 `read_cache` 字段
- `qt_ui/main_win/win_ui.ui`：移除 `cacheCheckBox` UI 元素（可选，保留也不影响功能，仅不再绑定逻辑）
- `server_process_start`：移除 `read_cache = server_config.get('read_cache', False)` 和 `server.start_server(read_cache=read_cache)` 的 `read_cache` 参数
