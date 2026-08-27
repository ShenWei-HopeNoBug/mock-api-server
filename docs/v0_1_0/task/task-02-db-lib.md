# 子任务 02 — MockDB 数据访问层（`lib/db_lib.py`）

## 目标

新建 `lib/db_lib.py`，实现核心类 `MockDB`，封装所有 SQLite 读写操作，替代原 JSON 文件读写逻辑。

## 涉及文件

- `lib/db_lib.py`（**新建**）

## 新增导入

```python
import sqlite3
import threading
from lib.utils_lib import generate_uuid, JsonFormat
```

> `generate_uuid` 和 `JsonFormat` 均来自 `lib/utils_lib.py`，分别用于 `upsert_api` 内部生成 id 和入库时 `params` 字段归一化。

## MockDB 方法清单

| 方法 | 用途 | id 来源 | 替代原函数 |
|---|---|---|---|
| `upsert_api(record)` → `id` | 新增插入（纯 INSERT，不去重），返回生成的 id | MockDB 内部 `generate_uuid()` | `add_user_api_data` |
| `batch_upsert_api(records)` | 批量写入（应用层去重后纯 INSERT） | record 中已有（mitmproxy 抓包时生成） | `save_response` (mitmproxy_lib) |
| `get_api_list(type=None, reverse=False)` | 查询列表（`type=None` 查全部，`type='MITMPROXY'` / `type='USER'` 按类型过滤；默认 `ORDER BY created_at ASC, id ASC`（最旧在前，与原 JSON 文件存储顺序一致），`reverse=True` 时改为 `DESC, id DESC`（最新在前，与原 `api_list[::-1]` 语义一致）） | — | `get_mitmproxy_api_data_list` / `get_user_api_data_list` |
| `update_api(record)` | 按 id 更新（`UPDATE ... WHERE id = ?`） | 调用方传入 | `update_user_api_data` |
| `delete_api(api_id)` | 按 id 删除 | 调用方传入 | `delete_user_api_data` |
| `batch_upsert_static(urls)` | 批量写静态资源（`ON CONFLICT(url) DO UPDATE SET updated_at`，重复抓取刷新更新时间） | — | `save_static` (mitmproxy_lib) |
| `get_static_list()` | 查静态资源列表（`ORDER BY created_at DESC, url DESC`） | — | `load_static_cache` |
| `close()` | 关闭 DB 连接，触发 SQLite 自动 checkpoint 将 `-wal` 合并回主库 | — | — |
| `_wal_checkpoint_passive()` | 内部辅助方法，执行 `PRAGMA wal_checkpoint(PASSIVE)`，供批量写入后调用 | — | — |

### id 生成职责下沉到 MockDB

`upsert_api`（新增场景）由 MockDB 内部调用 `generate_uuid()` 生成 id，调用方无需传 id，
避免前端传入原记录 id 导致复制操作变成更新原记录。
`update_api`（编辑场景）由调用方传入 id 定位记录。
`batch_upsert_api`（抓包场景）record 中的 id 由 `request_catch.py` 在 `response()` 阶段已生成。

## `close()` 方法说明

`close()` 关闭内部 `sqlite3.Connection`，连接关闭时 SQLite 自动执行 checkpoint 将 `-wal` 合并回主库。供子进程（`request_catch.py` 的 `done()`、`mock_server.py` 的 `create_api_dict`）以及主进程连接关闭函数（`app_lib._close_mock_db` / `app_lib.close_all_mock_db`）调用。

## `_wal_checkpoint_passive()` 方法说明

内部辅助方法，执行 `PRAGMA wal_checkpoint(PASSIVE)`，被动尝试将 `-wal` 合并回主库（不阻塞读写）。仅在 `batch_upsert_api` / `batch_upsert_static` 的 `finally` 块中调用，单条写入跳过（见下方「单条写入跳过 checkpoint 的原因」）。

## 入库时字段归一化

```python
# params 保持原始顺序（展示 + SIMPLE_MATCH 匹配）
params = JsonFormat.format_json_string(params)
```

### `params` 不排序存储的原因

`SIMPLE_MATCH` 模式下 `mock_server` 构建内存映射时走 `format_json_string`（不排序），
请求侧同样不排序，两侧靠**原始顺序一致**来命中。
若 `params` 列排序存储，则存储侧永远是排序序，请求侧保持原始序，两侧不一致导致命中失败。

> `params_md5` 不入库，由 `mock_server` 启动构建内存映射时根据当前 `http_params_match_mode` 实时计算，兼容 `EXACT_MATCH` 和 `SIMPLE_MATCH` 两种模式。

## `get_api_list` 返回格式

返回 `list[dict]`，每个 dict 包含 DB 中 `api_data` 表的**所有字段**：

```python
{
  'id': str,
  'type': str,           # MITMPROXY / USER
  'url': str,
  'method': str,
  'params': str,         # 原始顺序 json string
  'response': str,       # json string
  'created_at': str,     # 创建时间
  'updated_at': str,     # 更新时间
}
```

SQL（`type` 非 `None`，`reverse=False`）：`SELECT id, type, url, method, params, response, created_at, updated_at FROM api_data WHERE type=? ORDER BY created_at ASC, id ASC`

SQL（`type=None` 查全部，`reverse=False`）：`SELECT id, type, url, method, params, response, created_at, updated_at FROM api_data ORDER BY created_at ASC, id ASC`

`reverse=True` 时将 `ASC` 改为 `DESC`（`created_at DESC, id DESC`），返回最新记录在前。

`type=None` 时不加 `WHERE` 条件，返回 `MITMPROXY` 和 `USER` 的全部记录。当前 `get_mock_api_data_list` 为保持 USER 优先于 MITMPROXY 的覆盖语义仍采用两次查询合并（见 task-04），不使用 `type=None` 单次查询。`type=None` 供未来可能的「不分类型查全部」场景使用。

### 排序稳定性说明

`created_at` 精度到毫秒（`strftime('%Y-%m-%d %H:%M:%f','now','localtime')`），大幅降低批量写入时多条记录取到相同 `created_at` 值的概率。但毫秒仍非绝对唯一——高并发或批量 `executemany` 极快写入时仍可能碰撞，因此追加 `id ASC` 作为 tiebreaker，`id` 为 UUID 全局唯一，保证相同 `created_at` 的行有确定的排列顺序。`reverse=True` 时改为 `ORDER BY created_at DESC, id DESC`，保持双向排序的对称性。

> `reverse` 语义与原 JSON 实现对齐：`reverse=False`（默认）返回最旧记录在前（对应原 JSON 文件存储顺序），`reverse=True` 返回最新记录在前（对应原 `api_list[::-1]`）。`app_lib` 层直接透传 `reverse` 参数，无需反转。

相比原 JSON 数据格式新增了 `created_at` / `updated_at` 两个字段。
前端 / 预览页面只取 `id` / `type` / `url` / `method` / `params` / `response`，多出的字段不影响渲染。
`mock_server.create_api_dict` 始终从 `url` 实时计算 `route`（`remove_url_domain` + `remove_url_query`），不依赖 DB 冗余字段。

## 去重策略

DB 层不做自然键去重，`id` 为唯一主键，应用层去重保留在 `mitmproxy_lib.save_response_to_cache` 的内存缓冲阶段。三种写入场景分别为 INSERT ON CONFLICT、纯 INSERT 和 UPDATE，不依赖自然键唯一索引。

### mitmproxy 批量写入（`batch_upsert_api`）— 应用层去重后 INSERT ON CONFLICT

```sql
INSERT INTO api_data (id, type, url, method, params, response)
VALUES (?, 'MITMPROXY', ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
  url=excluded.url,
  method=excluded.method,
  params=excluded.params,
  response=excluded.response,
  updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
```

> 去重逻辑保留在 `mitmproxy_lib.save_response_to_cache` 的内存缓冲阶段（与当前行为一致），`done()` 时将去重后的 records 批量写入 DB。

#### 使用 `ON CONFLICT(id) DO UPDATE` 而非纯 INSERT 的原因

`load_history_cache` 从 DB 加载全部历史 MITMPROXY 记录到内存缓冲用于跨 session 去重。`done()` 时将**全部缓冲记录**（包括从 DB 加载的历史记录）批量写回 DB。历史记录的 `id` 已存在于 DB 中，纯 INSERT 会触发 `sqlite3.IntegrityError: UNIQUE constraint failed: api_data.id`。使用 `ON CONFLICT(id) DO UPDATE SET` 后：

- 历史记录（未重新抓取）→ 同 id 同数据，UPDATE 无实质变化，`created_at` 保留，`id` 不变
- 本轮新抓取的记录 → 新 id，正常 INSERT
- `id` 不在 SET 中，冲突时不会被修改
- `created_at` 不在 SET 中，冲突时保留原值
- `updated_at` 刷新不影响排序（排序用 `created_at`）

> 不使用 `INSERT OR REPLACE`，因为它会先 DELETE 旧行再 INSERT 新行，导致 `created_at` 被重置为当前时间，历史记录的创建时间丢失。

#### 批量写入采用单事务 + `executemany`

`batch_upsert_api` 将所有记录包裹在**一个事务**中，使用 `executemany` 批量执行：

```python
with self._lock:
  conn = self._conn
  conn.execute('BEGIN TRANSACTION')
  try:
    conn.executemany(sql, [(r['id'], r['url'], r['method'], r['params'], r['response']) for r in records])
    conn.execute('COMMIT')
  except Exception:
    conn.execute('ROLLBACK')
    raise
  finally:
    self._wal_checkpoint_passive()
```

- `executemany` 需要将 dict 列表转为 tuple 列表，`sqlite3.executemany` 不支持 dict 参数
- 整个批量只获取/释放一次 SQLite 文件写锁，commit 时间从 O(n) 次降为 O(1) 次，大幅缩短跨进程锁竞争窗口
- 事务保证原子性：要么全部写入成功，要么全部回滚，不会出现部分写入的中间状态
- WAL 模式下读写不互斥，批量写入期间主进程仍可正常读操作，仅在 `COMMIT` 的短暂瞬间有文件锁竞争
- commit 后执行 `PRAGMA wal_checkpoint(PASSIVE)` 合并 `-wal`（见 task-01 checkpoint 策略）

### user 新增/复制（`upsert_api`）— id 由 MockDB 内部生成，纯 INSERT

```sql
INSERT INTO api_data (id, type, url, method, params, response)
VALUES (?, ?, ?, ?, ?, ?)
```

- 每次调用均插入新记录，不去重，复制操作正常产生新记录

> id 由 MockDB 内部 `generate_uuid()` 生成，新增场景永远不会有 id 冲突。

### user 编辑（`update_api`）— 按 id 定位，先 SELECT 旧值再字段级合并后 UPDATE

```python
def update_api(self, record):
  with self._lock:
    conn = self._conn
    conn.execute('BEGIN TRANSACTION')
    try:
      # 1. 查询旧记录
      row = conn.execute(
        'SELECT type, url, method, params, response FROM api_data WHERE id=?',
        (record.get('id'),)
      ).fetchone()
      if row is None:
        conn.execute('ROLLBACK')
        return False

      # 2. 字段级合并：前端只传修改的字段时，旧值保留
      #    与原 update_user_api_data 的 `update_data.get('field') or o_data.get('field')` 语义一致
      old = {
        'type': row[0],
        'url': row[1],
        'method': row[2],
        'params': row[3],
        'response': row[4],
      }
      merged = {
        'type': record.get('type') or old['type'],
        'url': record.get('url') or old['url'],
        'method': record.get('method') or old['method'],
        'params': record.get('params') or old['params'],
        'response': record.get('response') or old['response'],
      }

      # 3. 写入合并后的完整记录
      conn.execute(
        '''UPDATE api_data SET
             type=?, url=?, method=?, params=?, response=?,
             updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
           WHERE id=?''',
        (merged['type'], merged['url'], merged['method'],
         merged['params'], merged['response'], record.get('id'))
      )
      conn.execute('COMMIT')
      return True
    except Exception:
      conn.execute('ROLLBACK')
      raise
```

```sql
-- SELECT 旧值
SELECT type, url, method, params, response FROM api_data WHERE id=?;
-- 合并后 UPDATE
UPDATE api_data SET
  type=?, url=?, method=?, params=?, response=?,
  updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
WHERE id=?;
```

### `delete_api` 实现

```python
def delete_api(self, api_id: str):
  with self._lock:
    conn = self._conn
    conn.execute('BEGIN TRANSACTION')
    try:
      cursor = conn.execute('DELETE FROM api_data WHERE id=?', (api_id,))
      if cursor.rowcount == 0:
        conn.execute('ROLLBACK')
        return False
      conn.execute('COMMIT')
      return True
    except Exception:
      conn.execute('ROLLBACK')
      raise
```

- `cursor.rowcount == 0` 表示未找到对应 id 的记录，回滚并返回 `False`
- 成功删除后 `COMMIT` 并返回 `True`
- `update_api` 和 `delete_api` 均需明确返回 `True`/`False`，因为 `app_lib` 中的调用方（`update_user_api_data` / `delete_user_api_data`）将返回值透传给前端，前端根据布尔值判断操作是否成功

#### `update_api` 采用 SELECT-merge-UPDATE 而非全字段覆盖的原因

原 `update_user_api_data` 的实现是字段级合并（`update_data.get('field') or o_data.get('field')`），
前端只传修改的字段时旧值会保留。若改为全字段直接覆盖，前端未传的字段会被写入 `None` / 空值，
导致数据丢失。因此在 `update_api` 中先 SELECT 旧记录，逐字段合并后再 UPDATE，
保持与原有部分更新语义完全一致。合并逻辑放在 `MockDB` 内部而非 `app_lib.py`，
使 `app_lib.update_user_api_data` 只需透传前端参数，无需感知合并细节。

#### `update_api` 无需冲突处理的原因

DB 层无自然键唯一索引，按 id 更新不会触发 `IntegrityError`，无需 delete + retry 逻辑。

#### `created_at` vs `updated_at` 分离的原因

新增 `updated_at` 列记录实际修改时间。`get_api_list` 按 `created_at` 排序保证展示顺序稳定。

### 单条写入跳过 checkpoint 的原因

`upsert_api` / `update_api` / `delete_api` 均为单行 DML，写入量小，`-wal` 增长有限。若每次写入后都执行 `PRAGMA wal_checkpoint(PASSIVE)`，用户在编辑弹窗中连续增删改多条记录时会产生不必要的 checkpoint I/O 开销。仅在 `batch_upsert_api` / `batch_upsert_static` 批量写入后执行 checkpoint 即可有效控制 `-wal` 增长，单条写入产生的 `-wal` 增量由后续批量 checkpoint 或应用退出时 `close()` 触发的最终 checkpoint 一并合并。

## `batch_upsert_static` 同样采用单事务 + `executemany`

与 `batch_upsert_api` 策略一致，将所有静态资源记录包裹在一个事务中批量执行：

```sql
INSERT INTO static_data (url, type) VALUES (?, 'MITMPROXY')
ON CONFLICT(url) DO UPDATE SET updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
```

```python
with self._lock:
  conn = self._conn
  conn.execute('BEGIN TRANSACTION')
  try:
    # records 为字符串列表（url 列表），executemany 要求每条记录为序列，需包装为单元素 tuple
    conn.executemany(sql, [(url,) for url in records])
    conn.execute('COMMIT')
  except Exception:
    conn.execute('ROLLBACK')
    raise
  finally:
    self._wal_checkpoint_passive()
```

- 单事务保证原子性，避免部分写入的中间状态
- `executemany` 批量执行，缩短跨进程锁竞争窗口
- commit 后执行 `PRAGMA wal_checkpoint(PASSIVE)` 合并 `-wal`
- **`executemany` 参数包装**：调用方（`request_catch.done()`）传入的是 `list[str]`（url 字符串列表），`sqlite3.executemany` 要求每条记录为序列（tuple/list），若直接传字符串会被当作字符序列——第一个字符被当作 `url` 参数写入，导致数据损坏。因此内部用 `[(url,) for url in records]` 将每个 url 包装为单元素 tuple
