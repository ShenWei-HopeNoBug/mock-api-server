# 子任务 06 — request_catch 改造

## 目标

将 `module/request_catch.py` 从 JSON 文件读写改为使用 `MockDB`，移除 `SimpleFolderBackup` 相关代码。

## 涉及文件

- `module/request_catch.py`

## 新增导入

```python
from lib.db_lib import MockDB
from config.work_file import DB_DATA_PATH
```

## `__init__` 改造

- `self.save_path` / `self.static_save_path` → `self.db_path = f'{work_dir}{DB_DATA_PATH}'`（与 `app_lib._get_mock_db` 中构造方式一致），初始化 `self.mock_db = MockDB(self.db_path)`
- `self.response_cache_dict` / `self.static_cache_dict` → 保留为内存缓冲

## `load_history_cache` 改造

从 DB 查询历史数据填充内存缓冲，保持跨 session 去重语义不变：

```python
def load_history_cache(self):
  # 从 DB 加载历史 response 数据，填充内存缓冲用于抓包去重
  mitmproxy_data = self.mock_db.get_api_list(type='MITMPROXY')
  for row_data in mitmproxy_data:
    mitmproxy_lib.save_response_to_cache(row_data, self.response_cache_dict)

  # 从 DB 加载历史静态资源数据，填充内存缓冲用于去重
  static_data = self.mock_db.get_static_list()
  for row_data in static_data:
    mitmproxy_lib.save_static_to_cache(row_data, self.static_cache_dict)
```

### `load_history_cache` 不能省略的原因

`save_response_to_cache` 的去重依赖内存缓冲 `response_cache_dict` 中已有的历史记录（以 `url+method` 为一级键、`md5(method+sort_params)` 为二级键）。
若仅初始化 `MockDB` 而不填充缓冲，每次抓包 session 的去重仅对当前 session 内有效，跨 session 重复抓同一接口会产生重复记录入库，导致 UI 列表出现重复条目、数据膨胀。
同理 `static_cache_dict` 需填充历史静态资源记录（以 `md5(url)` 为键），避免重复抓取同一静态资源 URL 入库。
因此 `load_history_cache` 改为从 DB 查询历史数据，遍历调用 `save_response_to_cache` / `save_static_to_cache` 填充缓冲，与原 `load_response_cache` / `load_static_cache` 的语义完全一致。

### DB 返回数据含额外字段的兼容性说明

`mock_db.get_api_list()` 返回的 dict 比 JSON 数据格式多了 `created_at` / `updated_at` 两个字段。`save_response_to_cache` / `save_static_to_cache` 内部只取 `id` / `type` / `url` / `method` / `params` / `response` 等字段构造缓存键，不会遍历整个 dict，额外字段不影响缓冲逻辑。但实施时需**验证 `save_response_to_cache` / `save_static_to_cache` 不会因额外字段报错**（如使用 `json.dumps` 序列化整个 dict 或解包全部字段的地方）。

## `done()` 改造

从内存缓冲提取记录批量写入 DB，写入完成后关闭连接：

```python
def done(self):
  print('mitmproxy done!')

  # 从 response_cache_dict 提取全部抓包记录
  # 缓冲结构: {search_key: {md5_key: record, ...}, ...}
  records = []
  for response_data in self.response_cache_dict.values():
    for record in response_data.values():
      records.append(record)

  print('----> 正在保存抓包数据，共 {} 条'.format(len(records)))
  self.mock_db.batch_upsert_api(records)
  self.response_cache_dict = {}

  # 从 static_cache_dict 提取全部静态资源 URL
  # 缓冲结构: {md5_key: record, ...}
  urls = [record.get('url') for record in self.static_cache_dict.values()]
  print('----> 正在保存静态资源数据，共 {} 条'.format(len(urls)))
  self.mock_db.batch_upsert_static(urls)
  self.static_cache_dict = {}

  # 批量写入完成后关闭连接，触发 SQLite 自动 checkpoint 将 -wal 合并回主库
  # mitmproxy 进程为"用完即关"，运行期间不再访问 DB
  self.mock_db.close()
```

### `done()` 中 `close()` 的必要性

`mitmproxy` 进程在 `done()` 后不再访问 DB。若不显式 `close()`，连接会随进程终止被隐式释放，
但隐式释放不保证执行 checkpoint，可能导致 `-wal` 文件残留。显式 `close()` 确保已提交事务的
`-wal` 内容被合并回主库，与连接管理策略中"mitmproxy 进程：`done()` 批量写入完成后 `close()` 连接"一致。

## 移除 `SimpleFolderBackup` 相关代码

- 移除 `from lib.backup_lib import SimpleFolderBackup` 导入
- 移除 `__init__` 中 `self.simple_folder_backup` 实例创建及 `source_dir` / `backup_dir` 相关变量
- 移除 `init()` 中 `self.simple_folder_backup.watch_diff_backup()` 调用
- 移除 `done()` 中 `self.simple_folder_backup.watch_diff_backup()` 调用
- 原因：WAL 模式下 `copytree` 复制 `mock.db` + `-wal` + `-shm` 侧车文件无法保证一致性，后续单独用 SQLite 原生 `backup()` API 或 `VACUUM INTO` 实现一致性快照
