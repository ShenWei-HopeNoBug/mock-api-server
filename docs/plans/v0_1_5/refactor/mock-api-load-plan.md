# mock api 数据加载查询收敛方案

> 关联文档：[PROJECT_REVIEW_REPORT](../../../reports/PROJECT_REVIEW_REPORT.md) §95 / §224（三次分类型全表查询 + 变体 N+1）；[TEST_GROUP_DESIGN_DISCUSSION](../../../discussions/TEST_GROUP_DESIGN_DISCUSSION.md) §2.2 优先级叙事 / §3 存量查询过滤点
> 状态：已实施（2026-11-10）
> 范围：`lib/app_lib.py` / `lib/db/api_data.py` / `lib/db/variants.py` / `app_types/db_types.py` / `config/enum/SERVER.py` / `module/mock_server.py` + 测试

## 1. 背景

`get_mock_api_data_list`（`lib/app_lib.py:218`）按 `MITMPROXY` → `MCP` → `USER` 分三次 `get_api_list` 查询拼接，目的是产出「类型优先级分段、段内 `created_at`/`id` 正序」的列表，配合 `create_api_map`（`module/mock_server.py:140`）`mock_api_map[request_key][response_key] = {...}` 的后者覆盖前者语义，实现 `USER > MCP > MITMPROXY` 优先级。同时 `create_api_map` 循环内逐行调用 `get_variants_by_api_id(api_data_id, enabled=True)`，每次执行 2 条 SQL（变体 + `response_variant_ids` 回查）且把 `response` 全文 SELECT 出来只取 `id`/`timeout`——数据量大时启动慢（评审台账已记录）。

调用点核实（全库 grep）：

| 调用方 | 参数 | 依赖的语义 |
|---|---|---|
| `module/mock_server.py:151` `create_api_map` | `enabled=True` | 分段顺序 → 覆盖优先级 + 段内正序；`response_key` 插入序（`_get_api_match_meta` 兜底取最后插入项） |
| `lib/download_lib.py:353` `_get_assets_list` | `enabled=None` | 仅需全量集合，顺序无关（结果经 `set()` 去重） |

未来类型扩展背景：`TEST_GROUP_DESIGN_DISCUSSION` 已明确第 4 类型 `TEST_GROUP` 要求 base_map **排除**组数据——「每加一类多一次查询」的写法扩展性差，白名单语义才是正确方向。

## 2. 决策

| 项 | 决定 |
|---|---|
| 三次查询收敛 | `ApiQuery` 新增 `api_types: Optional[List[str]]` 白名单字段 → `type IN (?,?,?)` 一次查询；`_build_api_where` 共用方法免费获得能力 |
| 优先级段序 | DB 返回 `created_at ASC, id ASC` 全局序后，Python **稳定排序**按 `MOCK_API_TYPE_PRIORITY` 重排——等价于三次查询拼接（段内相对序不变） |
| 优先级常量 | `SERVER.MOCK_API_TYPE_PRIORITY = ['MITMPROXY', 'MCP', 'USER']`，顺序即覆盖优先级；新增类型只改一行；白名单天然排除 `TEST_GROUP` |
| N+1 消除 | 新增 `get_variant_metas_by_api_ids(api_data_ids, enabled)` 批量查询，只 SELECT `id/api_data_id/timeout` 三列；调用方按行内已有 `response_variant_ids` 排序（无需回查） |
| IN 分片 | `chunk_size=500` 防御性分片（旧版 SQLite `SQLITE_MAX_VARIABLE_NUMBER=999`；当前环境 3.50.4 实测 32766，几乎不可能触线，约 5 行成本换免疫） |
| 失败粒度 | 批量查询在循环外执行，包 try/except 降级为空映射（所有接口走主响应兜底），对齐原「单行失败仅丢该行变体」的容错精神且不更差 |
| `get_variants_by_api_id` | 保留不动（`_fetch_variants` hook → `get_api_detail`、MCP 工具在用） |
| 实施方式 | 当前分支单 commit，不自动提交 |

## 3. 改动清单

### 3.1 `app_types/db_types.py`

`ApiQuery` 在 `api_type` 后追加字段；`ApiResponseVariant` 之后新增类型：

```python
api_types: Optional[List[str]]  # 数据来源类型白名单（type IN (...)），与 api_type 同传时取交集；空列表/None 不筛选
```

```python
class ApiResponseVariantMeta(TypedDict):
  """
  API response 变体轻量元数据

  用于 get_variant_metas_by_api_ids 的返回值，仅含 mock 匹配映射构建
  所需字段，不加载 response 大文本。
  """
  id: str  # 记录唯一标识
  api_data_id: str  # 所属 api_data 的 ID
  timeout: int  # idle 回退超时时间（毫秒），0 表示不启用
```

### 3.2 `lib/db/api_data.py` — `_build_api_where`

`api_type` 分支后追加（truthiness 判断，与 `url_like` 等字段一致）：

```python
api_types = query.get('api_types')
if api_types:
  placeholders = ','.join('?' * len(api_types))
  where_clauses.append(f'type IN ({placeholders})')
  sql_params.extend(api_types)
```

### 3.3 `lib/db/variants.py` — 新增方法（`get_variants_by_api_id` 之后）

```python
# 按 api_data_id 批量查询变体轻量元数据（不加载 response 大文本）
@_ensure_open(default=[])
def get_variant_metas_by_api_ids(
    self,
    api_data_ids: List[str],
    enabled: Optional[bool] = None,
) -> List[ApiResponseVariantMeta]:
  """按 api_data_id 批量查询变体轻量元数据，供 mock 匹配映射构建使用

  enabled=None 返回全部，True 仅启用，False 仅禁用。
  不做排序，组内顺序由调用方按 api_data.response_variant_ids 自行排列。
  """
  if not api_data_ids:
    return []

  enabled_sql = ''
  if enabled is True:
    enabled_sql = ' AND enabled=1'
  elif enabled is False:
    enabled_sql = ' AND enabled=0'

  result: List[ApiResponseVariantMeta] = []
  # SQLite 变量上限安全分片（兼容旧版 SQLITE_MAX_VARIABLE_NUMBER=999）
  chunk_size = 500
  with self._lock:
    for i in range(0, len(api_data_ids), chunk_size):
      chunk = api_data_ids[i:i + chunk_size]
      placeholders = ','.join('?' * len(chunk))
      rows = self._conn.execute(
        f'SELECT id, api_data_id, timeout FROM api_response_variants WHERE api_data_id IN ({placeholders}){enabled_sql}',
        chunk,
      ).fetchall()
      for row in rows:
        result.append({'id': row[0], 'api_data_id': row[1], 'timeout': row[2]})
  return result
```

### 3.4 `config/enum/SERVER.py` — `MOCK_API_DATA_DEFAULTS` 下方

```python
# mock api 数据加载的类型优先级（后者覆盖前者）
# create_api_map 按此顺序构建匹配映射，同 key 数据 USER 覆盖 MCP 覆盖 MITMPROXY
# 白名单语义：不在列表中的类型（如 TEST_GROUP）不参与 mock 匹配
MOCK_API_TYPE_PRIORITY = ['MITMPROXY', 'MCP', 'USER']
```

### 3.5 `lib/app_lib.py` — `get_mock_api_data_list` 重写

import 区新增 `from config.enum import SERVER`（`app_types` 与 `lib` 之间）。

```python
@error_catch(error_msg='读取 api 数据文件失败', error_return=[])
def get_mock_api_data_list(work_dir: str = '.', enabled: Optional[bool] = None) -> List[ApiData]:
  """按 MOCK_API_TYPE_PRIORITY 白名单一次查询 mock api 数据

  返回顺序 = 类型优先级分段，段内 created_at/id 正序，供 create_api_map
  「同 key 后者覆盖前者」语义使用；白名单外类型（如 TEST_GROUP）不参与。
  """
  mock_db: MockDB = MockDBCache.get(work_dir)
  api_list = mock_db.get_api_list(
    query=ApiQuery(api_types=SERVER.MOCK_API_TYPE_PRIORITY, enabled=enabled),
    reverse=False,
  )
  # 稳定排序仅按类型优先级重排，段内保持 DB 返回的 created_at/id 正序
  type_order = {t: i for i, t in enumerate(SERVER.MOCK_API_TYPE_PRIORITY)}
  api_list.sort(key=lambda data: type_order.get(data['type'], len(type_order)))
  return api_list
```

### 3.6 `module/mock_server.py` — `create_api_map`

import：`ApiResponseVariant` → `ApiResponseVariantMeta`。

`mock_db` 获取后、for 循环前插入批量加载（含降级）：

```python
# 一次批量查询全部启用变体的轻量元数据并按 api_data_id 分组（id 键保持查询序），
# 替代逐行 get_variants_by_api_id 的 N+1 查询与 response 大文本加载；
# 查询失败时降级为空映射，所有接口走主响应兜底而非整个 map 构建失败
variant_metas_by_api: Dict[str, Dict[str, ApiResponseVariantMeta]] = {}
try:
  api_data_ids: List[str] = [row['id'] for row in mock_api_data_list]
  for m in mock_db.get_variant_metas_by_api_ids(api_data_ids, enabled=True):
    variant_metas_by_api.setdefault(m['api_data_id'], {})[m['id']] = m
except Exception as e:
  MOCK_LOGGER.warning(f'变体元数据批量查询失败，全部接口降级为主响应：{e}')
```

循环内替换原 `get_variants_by_api_id` 调用块（保留排序语义）：

```python
# 启用的变体元数据列表（按 response_variant_ids 顺序，未在列表中的排最后）
order_map = {v: i for i, v in enumerate(data['response_variant_ids'])}
variant_metas: List[VariantMeta] = [
  {'id': m['id'], 'timeout': m['timeout']}
  for m in sorted(
    variant_metas_by_api.get(api_data_id, {}).values(),
    key=lambda m: order_map.get(m['id'], len(order_map)),
  )
]
```

### 3.7 测试

| 文件 | 用例 |
|---|---|
| `tests/lib/db/test_api_data.py` 追加 | `test_api_types_filter`：4 类型数据，`api_types=['USER','MCP']` 只回两类（`TEST_GROUP` 即白名单排除的回归护栏） |
| `tests/lib/db/test_variants.py` 追加 | `test_get_variant_metas_by_api_ids`：启用/禁用过滤、仅 3 字段、空入参返回 `[]` |
| `tests/lib/test_app_lib.py` 新建 | 混插 3 类型后断言分段序：全部 MITMPROXY < 全部 MCP < 全部 USER（跨类型段序确定，不受 `created_at` 平局影响） |

## 4. 影响面（已核实）

| 调用方/共用方 | 依赖 | 结论 |
|---|---|---|
| `create_api_map` | `get_mock_api_data_list` 顺序 | 逐行等价（§5） |
| `download_lib._get_assets_list` | `get_mock_api_data_list` 全量集合 | 等价；白名单外类型新旧均不返回 |
| `mcp_server.py:167` / `qt_win/mitmproxy_data_edit_dialog.py` / 既有测试 | `ApiQuery` 构造 | `api_types` 为 `total=False` 可选字段，不传零影响 |
| `get_api_list_page`/`get_api_count`/`batch_delete_api` | 共用 `_build_api_where` | 顺带获得 `api_types` 能力，属能力扩展非行为变化 |
| `get_variants_by_api_id` 现存调用方 | `_fetch_variants` hook、MCP 工具、测试 | 方法保留，不动 |
| schema / 数据 / 协议 / 前端 | — | 无 DDL、无迁移、无桥接协议变化、Web 端 `ApiType` 不变 |

## 5. 行为等价清单（实施时逐行对照项）

- 列表顺序：`type IN` + `created_at ASC, id ASC` + 稳定排序 == 三次 `type =` 查询拼接（同类型元素相对序不变）；
- `response_key` 插入序不变 → `_get_api_match_meta` 的 `next(reversed(inner))` 兜底项不变；
- 变体过滤：批量 `enabled=1` == 原逐行 `enabled=True`；
- 变体排序：`order_map.get(v['id'], len(order_map))` 孤儿启用变体排尾、稳定排序保持查询序 == 原 `variants.py:274`；
- `response_variant_ids` 中禁用/失效 id：`order_map` 有键而分组无值，跳过 ✓；
- `enabled=None` 语义不变（不加 `enabled` 条件）。

## 6. 提交拆分

单 commit：`refactor(mock): mock api 数据加载查询收敛（IN 白名单 + 变体批量元数据）`，含代码 + 测试 + 本方案文档 + `docs/plans/README.md` 登记。不自动提交。

## 7. 验收

```bash
uv run ruff check .    # 归零
uv run pytest          # 全绿
```

| 项 | 方式 |
|---|---|
| 顺序等价 | `test_app_lib.py` 分段序断言 + 逐行 diff 对照 §5 |
| N+1 消除 | `create_api_map` 查询次数 `3+2N` → `1+⌈N/500⌉`，DB 日志观察 |
| 冒烟（可选） | 启动 mock 服务，混类型数据命中验证（含变体轮播） |

## 8. 明确不做

- `get_api_list` 列裁剪（`create_api_map` 不需要 `response` 列）——收益次于本方案，视数据量级另行立项；
- `(enabled, type)` 复合索引——当前量级 `idx_api_type` + filesort 足够；
- `download_lib` 改单次全表查询——白名单语义更稳，维持现状；
- `TEST_GROUP` 本体落地——本方案仅保证白名单兼容，组功能走自身立项。

## 9. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-10 | 按 §3.1–3.7 全部实施 | `ruff check` 归零 + `pytest` 127 过 1 skip | `test_app_lib.py` 增补 `enabled` 过滤用例；`PROJECT_REVIEW_REPORT` 追加「处理进展：2026-11-10」台账 |

## 10. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| - | - | - |
