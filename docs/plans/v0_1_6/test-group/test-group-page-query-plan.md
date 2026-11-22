# 测试组列表分页/筛选 + 启用组查询桥协议扩展方案（Qt 侧）

> 关联文档：上游总体方案 [test-group-plan](test-group-plan.md)（测试组语义、schema、匹配层）；web 侧实施见 `mock-api-server-web-v3` 仓 `docs/plans/v0_1_6/test-group/test-group-page-query-web-plan.md`
> 状态：待实施
> 范围：`lib/db/test_group.py` / `app_types/{db_types,app_gui_types}.py` / `qt_win/mitmproxy_data_edit_dialog.py` / `docs/reference/QT_BRIDGE.md` / `tests/lib/db/test_test_group.py`

## 1. 背景与范围

web 侧 testGroupManager 组列表现经 `/test_group/list` 无参全量拉取，无分页与筛选能力。为支撑组名筛选及后续复杂查询扩展，新增**分页查询**与**启用组简略信息**两条增量桥方法。

**本仓做**：`/test_group/page`、`/test_group/enabled` 两条增量协议；`TestGroupQuery` 查询对象 + DB 分页/计数/启用组摘要三个新方法；handler 与类型；测试；`QT_BRIDGE.md` 登记。

**本仓不做**：web 侧 UI 与数据流（见 web 仓方案）；`/test_group/list` 存量语义（GroupPickerDialog 等调用方不动）。

## 2. 决策汇总

| 决策点 | 结论 |
|---|---|
| 分页方法形态 | **新增 `/test_group/page`**，不改 `/test_group/list`：纯增量零兼容风险；避免单方法「分页/全量」双形态载荷；存量全量消费方（GroupPickerDialog）零改动 |
| 启用组返回形态 | `/test_group/enabled` 无参，**直返 `Optional[TestGroupSummary]`**：对齐 `/test_group/detail` 直返 `Optional` 惯例，不包 `{group}` 壳；无启用组返回 `None` |
| 查询对象 | 新增 `TestGroupQuery`（db_types）：字段全 Optional，对齐 `ApiQuery` 模式——后续加筛选字段仅扩 TypedDict + where 构建 |
| enabled 脏数据 | where 构建对 `enabled` 只做 True/False 过滤，**不修复**多行 `enabled=1` 脏数据（不变量由 enable/disable 原子写保证，查询侧不干预） |
| count 查询 | `COUNT(*)` 只查 `test_group` 单表，不经 LEFT JOIN（当前 where 字段均在 g 表；未来若引入 join 侧筛选字段再演进） |

## 3. 协议契约（权威定义，web 侧以本节为准）

| 请求名 | 参数 | 返回 | 备注 |
|---|---|---|---|
| `/test_group/page` | `{name?, enabled?, page_num?, page_size?}` | `{list: [TestGroupSummary], total, page_num, page_size}` | name 模糊匹配；enabled 仅 bool 生效；默认 `page_num=1, page_size=20` |
| `/test_group/enabled` | `{}` | `TestGroupSummary \| null` | 当前启用组简略信息（含 item_count）；无启用组返回 `null` |

`TestGroupSummary` 字段集与 `/test_group/list` 行一致（id/name/enabled/operator/created_at/updated_at/item_count）。

## 4. DB 层（`lib/db/test_group.py` 增量）

| 方法 | 语义 |
|---|---|
| `_build_test_group_where(query)` | `name_like` → `g.name LIKE ?`（`%...%`）；`enabled is True` → `g.enabled=1` / `is False` → `g.enabled=0`；返回 `(where_sql, sql_params)`，对齐 `_build_api_where` 结构 |
| `get_test_group_count(query)` | `SELECT COUNT(*) FROM test_group g {where}` |
| `get_test_group_list_page(query, page_num=1, page_size=20)` | 现有 LEFT JOIN `item_count` SQL 前插 where，末尾 `LIMIT ? OFFSET ?`；`ORDER BY created_at DESC, id DESC` 保持 |
| `get_enabled_test_group_summary()` | 同 LEFT JOIN 结构 + `WHERE g.enabled=1 LIMIT 1` → `Optional[TestGroupSummary]` |

`get_test_group_list()` / `get_enabled_test_group_id()` 原样保留，零改动。

## 5. 类型与参数

- `app_types/db_types.py`：`TestGroupQuery` TypedDict——`name_like`、`enabled` 全 Optional，逐字段注释（对齐 `ApiQuery`/`TestGroupSummary` 注释密度），注释注明预留扩展位（operator、时间区间等后续直接加 key）。
- `app_types/app_gui_types.py`：`GetTestGroupPageParams`（total=False：`name`/`enabled`/`page_num`/`page_size`）；`TestGroupPageResult`（`list`/`total`/`page_num`/`page_size`）。`/test_group/enabled` 无入参、返回复用 `db_types.TestGroupSummary`，**不新增 TypedDict**。

## 6. Handler（`qt_win/mitmproxy_data_edit_dialog.py`）

- `_handle_get_test_group_page`：对齐 `_handle_get_mock_data_page` 写法——`page_num=params.get('page_num', 1)`、`page_size=params.get('page_size', 20)`；`name → name_like`（`or None`）；`enabled` 经 `isinstance(enabled, bool)` 守卫后入 query；先 `get_test_group_count` 再 `get_test_group_list_page`，返回 `{list, total, page_num, page_size}`。
- `_handle_get_enabled_test_group`：一行透传 `mock_db.get_enabled_test_group_summary()`。
- `_REQUEST_HANDLERS` 注册 `'/test_group/page'`、`'/test_group/enabled'`。

## 7. `docs/reference/QT_BRIDGE.md` 登记

`/test_group/*` 协议表补两行（§3 契约同构）。

## 8. 测试（`tests/lib/db/test_test_group.py` 补用例）

| 用例 | 断言 |
|---|---|
| `name_like` 模糊 | 命中子串组、不命中其他组 |
| `enabled` 过滤 | True 至多 1 行且 enabled；False 排除启用组 |
| 分页边界 | page 越界 → `list` 空、`total` 不变；`page_size` 截断正确 |
| 无参查询 | `TestGroupQuery()` 等价全量（与 `get_test_group_list` 同集） |
| 启用组摘要 | 启用后返回该组且 `item_count` 正确；无启用组返回 `None` |

## 9. 影响面（本仓）

| 文件 | 改动 |
|---|---|
| `app_types/db_types.py` | `TestGroupQuery` 新增 |
| `lib/db/test_group.py` | where 构建 + 分页/计数/启用组摘要三方法 |
| `app_types/app_gui_types.py` | `GetTestGroupPageParams` / `TestGroupPageResult` |
| `qt_win/mitmproxy_data_edit_dialog.py` | 两 handler + `_REQUEST_HANDLERS` 两行 |
| `docs/reference/QT_BRIDGE.md` | 协议表两行 |
| `tests/lib/db/test_test_group.py` | 补用例 |

**零改动**：`get_test_group_list`（GroupPickerDialog 全量）、`get_enabled_test_group_id`（mock 子进程每请求调用）、匹配层、`/test_group/*` 其余 handler、`web-v3` 构建产物。

**版本配套**：两条为增量契约，新 web 产物依赖新 Qt 构建——发布天然同批；联调注意不可新 web 配旧 exe。

## 10. 实施节奏

与 web 侧同批落地。完成 → 报验收 → 等确认 → commit。**不自动提交**。

## 11. 验收

```bash
uv run ruff check .    # 归零
uv run pytest          # 全绿
```

| 项 | 方式 |
|---|---|
| 分页/筛选 | `test_test_group` 新用例 + 手测：桥调用 `/test_group/page` 各参数组合 |
| 启用组摘要 | 用例 + 手测：启用/停用/顶替后 `/test_group/enabled` 返回符合预期 |
| 存量回归 | `/test_group/list` 全量不变；mock 子进程启用匹配不受影响 |

## 12. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-22 | TestGroupQuery + 分页/计数/启用组摘要三方法 + 两 handler + QT_BRIDGE.md 登记 + 5 用例 | ruff 改动文件 0 错误；pytest 177 passed / 1 skipped | 未提交，待确认 |

## 13. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| — | — | — |
