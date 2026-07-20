# 子任务 04 — app_lib 改造

## 目标

将 `lib/app_lib.py` 中的 CRUD 函数从 JSON 文件读写改为调用 `MockDB`，新增模块级懒加载单例缓存和连接关闭函数。

## 涉及文件

- `lib/app_lib.py`

## 新增模块级懒加载单例

按 `work_dir` 绝对路径缓存 `MockDB` 实例：

```python
from lib.db_lib import MockDB
from config.work_file import DB_DATA_PATH

_mock_db_cache: dict = {}

def _get_mock_db(work_dir: str = '.') -> MockDB:
  cache_key = os.path.abspath(work_dir)
  if cache_key not in _mock_db_cache:
    db_path = f'{work_dir}{DB_DATA_PATH}'
    _mock_db_cache[cache_key] = MockDB(db_path)
  return _mock_db_cache[cache_key]
```

### 缓存 key 用绝对路径的原因

`work_dir` 参数可能传入 `'.'`、`'./server'`、`'./server/'` 等不同相对路径形式，但实际指向同一目录。用 `os.path.abspath(work_dir)` 归一化为绝对路径作为缓存 key，避免同一目录创建多个 `MockDB` 实例和多个 DB 连接。

### `server_lib.py` 中的 `get_static_data_list` 同理

`server_lib.py` 的 `get_static_data_list` 也接收 `work_dir` 参数，改用 `MockDB` 后同样通过 `app_lib._get_mock_db(work_dir)` 获取实例，复用同一缓存，避免独立创建连接。

## CRUD 函数改造

- `get_mitmproxy_api_data_list` → 内部改 `_get_mock_db(work_dir).get_api_list(type='MITMPROXY', reverse=reverse)`，签名不变
- `get_user_api_data_list` → `_get_mock_db(work_dir).get_api_list(type='USER', reverse=reverse)`
- `get_mock_api_data_list` → 保持两次查询合并，与当前行为一致（签名 `get_mock_api_data_list(work_dir='.')` 不变，无 `reverse` 参数，`get_api_list` 默认按 `created_at DESC` 排序已满足需求）：

```python
mock_db = _get_mock_db(work_dir)
api_list = mock_db.get_api_list(type='MITMPROXY')
api_list.extend(mock_db.get_api_list(type='USER'))
return api_list
```

### 不改为单次 `get_api_list()` 查询的原因

当前实现 `mitmproxy_list.extend(user_list)` 使 USER 数据在后，`create_api_dict` 遍历时后写入覆盖先写入，即 USER 永远优先于 MITMPROXY。若改为单次 `ORDER BY created_at` 查询，同路由记录的覆盖优先级由 `created_at` 决定而非 type，会导致用户手动编辑的 USER 数据被旧的 MITMPROXY 数据覆盖。两次查询合并保持原有优先级语义，零回归风险。

- `save_user_api_data_list` → 废弃
- `add_user_api_data` → 构造 record（不含 id）→ `mock_db.upsert_api(record)`，id 由 MockDB 内部生成
- `update_user_api_data` → 构造 record（含 id）→ `mock_db.update_api(record)`
- `delete_user_api_data` → `mock_db.delete_api(api_id)`
- `fix_user_api_data` → 改为 no-op 直接返回 `True`（SQLite schema 的 `NOT NULL DEFAULT` + `PRIMARY KEY` 已保证数据完整性，不存在字段缺失/id 缺失问题；保留函数签名避免前端 `fix_mock_data` 事件调用报错，后续前端移除按钮时再一并清理）

## 移除的导入

- 移除 `import pandas`
- 移除 `from config.enum.MITMPROXY import MITMPROXY_DATA_FIELDS`
- 移除 `from lib.utils_lib import fix_dict_field`

## 新增连接关闭函数

### `_close_mock_db(work_dir)`

从 `_mock_db_cache` 中取出对应 `MockDB` 实例并 `close()`，同时从缓存中移除。供 `mock_server` 进程的 `create_api_dict` 在读取完成后调用，确保子进程连接及时关闭：

```python
def _close_mock_db(work_dir='.'):
  cache_key = os.path.abspath(work_dir)
  mock_db = _mock_db_cache.pop(cache_key, None)
  if mock_db:
    mock_db.close()
```

### `close_all_mock_db()`

遍历 `_mock_db_cache` 关闭所有缓存的 `MockDB` 实例并清空缓存。供主进程 `qt_win/app.py` 的 `closeEvent` 在应用退出时调用，触发最终 checkpoint：

```python
def close_all_mock_db():
  for mock_db in _mock_db_cache.values():
    mock_db.close()
  _mock_db_cache.clear()
```

## 不变的部分

- 函数签名保持不变，调用方无需改动
