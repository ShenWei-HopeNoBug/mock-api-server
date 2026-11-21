# 测试组功能开发方案（Qt 侧总方案）

> 关联文档：[TEST_GROUP_DESIGN_DISCUSSION](../../../discussions/TEST_GROUP_DESIGN_DISCUSSION.md)（概念与决策源流）；web 侧实施见 `mock-api-server-web-v3` 仓 `docs/plans/v0_1_6/test-group/test-group-web-plan.md`
> 状态：待实施
> 范围：`schema/v6.sql` / `lib/db/*` / `app_types/*` / `config/enum/*` / `module/mock_server.py` / `lib/server_lib.py` / `qt_win/mitmproxy_data_edit_dialog.py` / `module/mcp_server.py`（兜底一处）/ `tests/`

## 1. 背景与范围

「测试组」= 一组 mock 接口数据（含变体）的命名集合，可一键启用/停用，启用期间组数据在同 key 处遮蔽底层数据（`TEST_GROUP(启用组) > USER > MCP > MITMPROXY`）。讨论稿的全部概念决策沿用，本方案负责裁剪与落地细化。

**本期做**：schema v6、组 CRUD + 原子启用、拷入组（双入口）、**启用组单份快照装载（启动即冻结）**+ 遮蔽解析、GUI 管理页签（唯一控制面）、存量查询过滤修正。

**本期缓**：`__mock_did`（cookie/query 传 device_id）、`pinned_variant_id`（pin 语义列）、MCP 工具面、编排期全部（`test_step`/`test_run`/`test_run_step` 表结构与字段、`begin_test_run`/`report_step_result`/`finish_test_run`、步骤编辑 UI、执行协议）。

## 2. 决策汇总

| 决策点 | 结论 |
|---|---|
| group_map 加载 | **启动仅装载当前启用组单份快照**（无启用组 → None）；组数据与启用态进程内一律冻结，启用/停用/顶替/条目增删改全部需重启 mock 服务生效（热更新立项消解）；休眠组零内存占用 |
| schema | 只建本期必需：`api_data + group_id`（唯一新列）+ `test_group` 极简表；编排期结构随该期设计再迁移 |
| 遮蔽粒度 | 精确 `(request_key, response_key)`；组内 miss 且 base 有同 request_key → 落回 base；base 无 → 组内末位兜底（base 宽松规则在组 map 内原样复用，仅用于组独有接口）；404 仅在 request_key 整体 miss |
| 变体机制 | 零新机制：sequence 复用现有 device_id 轮播；「固定返回变体 X」 = 排他启用单变体 + device_id |
| item enabled | 两级生效：组启用 ∧ item enabled=1 才参与遮蔽（建图即过滤） |
| 拷入组 | `copy_variants` 默认 True（连变体带 enabled/顺序拷）；item enabled 按入口分默认：outputManager 推入默认禁 / 组详情拉取默认启 |
| group_id | 创建后不可变（同 `type` 规制；移组 = 拷入新组 + 删除旧条目） |
| 控制面 | 唯一入口：dataManager 弹窗 BasicLayout + 页签 |
| 实施节奏 | 三步走，每步完成停下等确认，确认后 commit 进下一步 |

## 3. Schema v6

`schema/v6.sql` 新建 + `lib/db/constants.py` `CURRENT_SCHEMA_VERSION → 6`：

```sql
-- api_data 迁移列（唯一新列）
group_id  TEXT,    -- 仅 type='TEST_GROUP' 行有值，创建后不可变

CREATE TABLE test_group (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL DEFAULT '',
  enabled    INTEGER NOT NULL DEFAULT 0,   -- 全局至多一行 1
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);
CREATE INDEX idx_test_group_enabled ON test_group(enabled);
```

索引说明：量级上非必需（组行数十量级，全表扫描亦微秒级），保留理由是约定一致性——`idx_api_type` 同型先例（低基数标志列 + 「按标志查」访问模式），enabled 是启动时装载与 GUI 列表的查询键。

迁移：`ApiDataMixin._migrate_api` 追加 `from_version < 6` 块（`_column_exists` 守卫）；`TestGroupMixin._migrate_test_group` 建表（幂等，对齐 `_migrate_variant` 建表先例）；`MockDB._migrate_schema` 增调一行。

## 4. DB 层

### 4.1 新 `lib/db/test_group.py` `TestGroupMixin`（挂 `MockDB`）

| 方法 | 语义 |
|---|---|
| `insert_test_group(record)` | name + operator；返回 id |
| `update_test_group(record)` | name 字段级合并；`enabled` 不可经此改 |
| `delete_test_group(group_id)` | 一事务级联：组内 api 的 variants → `api_data WHERE group_id` → `test_group` 行 |
| `get_test_group(group_id)` | 组详情 + items（`api_type='TEST_GROUP' AND group_id`） |
| `get_test_group_list()` | `LEFT JOIN` 带出 `item_count` |
| `get_enabled_test_group_id()` | `SELECT id WHERE enabled=1`，mock 子进程每请求调用 |
| `enable_test_group(group_id)` | 一事务 `enabled=0` 全清 + `enabled=1` 置目标（原子顶替） |
| `disable_test_group()` | 无参；`UPDATE test_group SET enabled=0` 全清（含不变量自修复） |
| `copy_api_to_group(api_id, group_id, copy_variants=True, enabled, operator)` | 一事务：拷业务字段 → `type='TEST_GROUP'`、`group_id`、`enabled` 按入参；带变体则按源 `response_variant_ids` 顺序拷变体行（保留 enabled，type/operator 记操作者）并重建绑定列表 |

命名注：`enable`/`disable` 与讨论稿 §6 MCP 工具面词汇对齐，未来 MCP 工具直接透传本层；`disable` 无参表「清掉当前启用态」，顺带修复「多行 enabled=1」的不变量破损。

### 4.2 `lib/db/api_data.py`

- `_migrate_api` 追加 v6 块；
- `insert_api`/`batch_insert_api`/`update_api`/`get_api_list`/`get_api_list_page`/`get_api_detail` 的列清单与行映射补 `group_id`；
- `_build_api_where` 加 `group_id = ?` 过滤；
- `update_api` 合并排除 `group_id`（同 `type` 创建后不可变规制）。

### 4.3 类型与常量

`app_types/db_types.py`：`ApiRecord`/`ApiData`/`ApiDataDetail`/`ApiQuery` 补 `group_id`；新增 `TestGroup` 系列 TypedDict（`TestGroupRecord`/`TestGroup`/`TestGroupSummary`/`TestGroupDetail`）。**字段逐字段注释完整**——含义、默认值、取值约束、创建后可不可变；dict/list 字段元素结构写清（如 `TestGroupDetail.items` 元素类型直接复用 `ApiData`，`get_test_group_list` 返回 `List[TestGroupSummary]`），对齐现有 `ApiData`/`ApiResponseVariant` 注释密度。

`config/enum/SERVER.py` `MOCK_API_DATA_DEFAULTS`、`config/enum/DATABASE.py` `API_INSERT_DEFAULTS` 补 `group_id` 默认值。

## 5. 匹配层

### 5.1 `module/mock_server.py` `create_api_map`

- 抽公共「行 → ApiMatchMeta」建行逻辑（route 处理、request_key/response_key 生成、变体元数据排序）；
- `base_map`：现白名单逻辑零改动（`MOCK_API_TYPE_PRIORITY` 天然排除 TEST_GROUP）；
- `group_map: Optional[MockApiMap]`：启动时 `get_enabled_test_group_id()` 读一次，有启用组则仅查 `api_type='TEST_GROUP' AND group_id=启用组 AND enabled=1` 行建单组内层 map；无启用组/查询异常 → None。组内 `created_at` 序保持「后者覆盖前者」。

### 5.2 `lib/server_lib.py` `MockRequestHandler`

注入 `group_api_map`（启动快照，进程内不变），新增 `_resolve_meta` 替换原 `_get_api_match_meta` 调用点。**组解析路径零 DB 访问**——无启用态读、无热重载：

```python
# _resolve_meta(request_key, response_key)
inner = self.group_api_map                     # 启动快照；None → 直接 base 解析
if inner 含 request_key:
    精确 response_key 命中 → 组 meta                    # 遮蔽生效
    未命中 且 base 无此 request_key → 组内末位 fallback    # 组独有接口
    base 有同 request_key → 落回 base 正常解析            # 精确遮蔽原则
base：既有 精确 → 末位 fallback 不变
```

`handle()`/`ApiMatchMeta`/变体轮播/device_id 头：**零改动**。

## 6. 过滤修正（存量坑，本期必修）

`_handle_get_mock_data_page`/`_handle_batch_delete_mock_data`（`qt_win/mitmproxy_data_edit_dialog.py`）：`type` 未指定/非法时 `api_type=None` → 无类型过滤，TEST_GROUP 数据会漏进主列表、被批删误伤。修正：此时兜 `api_types=SERVER.MOCK_API_TYPE_PRIORITY` 白名单。MCP `list_mock_apis`（`module/mcp_server.py`）同兜底——防御性修正，不加新工具；显式 `api_type='TEST_GROUP'` 仍可查。

## 7. Qt Bridge 协议扩展

`MitmproxyDataEditDialog._REQUEST_HANDLERS` 新增（`app_gui_types.py` 补参数类型，`docs/reference/QT_BRIDGE.md` 登记）：

| 请求名 | 参数 | 返回 | 备注 |
|---|---|---|---|
| `/test_group/list` | `{}` | `{list: [TestGroupSummary]}` | 含 item_count/enabled |
| `/test_group/detail` | `{id}` | `TestGroupDetail` | 组字段 + items 完整列表 |
| `/test_group/create` | `{name}` | `{id}` | operator='USER' |
| `/test_group/update` | `{id, name}` | OperationResult | 仅 name 可改 |
| `/test_group/delete` | `{id}` | OperationResult | 级联删 |
| `/test_group/enable` | `{id}` | OperationResult | 原子顶替 |
| `/test_group/disable` | `{}` | OperationResult | 全清 |
| `/test_group/copy_into` | `{api_id, group_id, copy_variants, enabled}` | `{id}` | 返回新 item id |

组 item 编辑/删除/变体操作复用 `/mock_data/*`、`/variant/*` 现有协议（组 item 本质 api_data 行，`update_api` 直通）。

## 8. 测试

| 文件（tests/ 镜像结构） | 用例 |
|---|---|
| `test_test_group.py`（新） | 组 CRUD、原子顶替（启用后全局仅一行 enabled=1）、级联删、`copy_api_to_group` 带/不带变体、enabled 入参 |
| `test_api_data.py` | v6 迁移幂等、update 不改 `group_id`、`group_id` 过滤 |
| `test_server_lib.py` | 遮蔽解析序（组精确赢 / base 同 key 时组 miss 落回 / 组独有接口末位兜底 / base fallback 不变 / 无快照走 base）、组路径零 DB 访问断言、快照冻结（启用态 DB 标志变更不影响解析）、404 语义不变 |
| `test_app_lib.py` | 白名单兜底回归（无类型条件不回 TEST_GROUP 行） |

## 9. 实施节奏（逐步确认制）

| 步骤 | 内容 | 节奏 |
|---|---|---|
| ① | schema v6 + TestGroupMixin + `api_data.group_id` 扩展 + 过滤修正 + 测试 | 完成 → 报验收 → 等确认 → commit |
| ② | 匹配层：双层 map + 遮蔽解析 + 测试 | 同上 |
| ③ | Qt bridge handlers（web 侧页面随后端同批，见 web 方案） | 同上 |

每步完成**不自动 commit**：报 `ruff`/`pytest` 结果与手动验证点，确认或提出调整后再提交。

## 10. 影响面（本仓）

| 文件 | 改动 |
|---|---|
| `schema/v6.sql`（新）、`lib/db/constants.py` | schema v6、版本号 |
| `lib/db/test_group.py`（新）、`lib/db/mock_db.py` | TestGroupMixin 挂载 + 迁移调度 |
| `lib/db/api_data.py` | 列清单/行映射/where 构建/update 排除 |
| `app_types/db_types.py`、`app_types/app_gui_types.py` | TypedDict 新增/扩展 |
| `config/enum/SERVER.py`、`config/enum/DATABASE.py` | 默认值补齐 |
| `module/mock_server.py`、`app_types/mock_server_types.py` | `create_api_map` 双层产出（group_map 为启用组单份快照） |
| `lib/server_lib.py` | `_resolve_meta` 双层遮蔽（组快照直读，组路径零 DB） |
| `qt_win/mitmproxy_data_edit_dialog.py` | 过滤白名单兜底 + `/test_group/*` handlers |
| `module/mcp_server.py` | `list_mock_apis` 白名单兜底一处 |
| `docs/reference/QT_BRIDGE.md` | `/test_group/*` 协议登记 |
| `tests/` | 镜像结构补用例 |

**零改动**：mitmproxy 抓包链路、`download_lib`（白名单天然排除组数据，组响应不参与资源下载——符合预期）、`static_data`、`app_server`。

## 11. 明确不做 / 遗留

| 项 | 说明 |
|---|---|
| `__mock_did` | cookie/query 传 device_id 的入口优化，编排期配套再做 |
| `pinned_variant_id` | pin 便捷语义（无 device_id 命中变体 + 变体 enabled 态保留）；本期用「排他启用单变体 + device_id」等效 |
| MCP 工具面 | 组 CRUD/enable/disable/add_api_to_test_group 及 `update_mock_api` 扩展；核心功能验证可靠再开放 |
| 编排期全部 | test_step/test_run/test_run_step 结构与 test_group 扩展列，随该期设计一并迁移 |
| 组热更新/热切换 | 「启动即冻结」：启用/停用/顶替与组数据增删改均需重启 mock 服务生效；热切换/热更新后续统一立项设计 |
| 纯净模式 | 组级 flag（启用期间仅组内数据响应） |
| 多组启用 | `priority` 消解与 UI 提示 |
| 遮蔽表达 404 | 等自定义状态码能力根治，变通用错误响应变体 |

## 12. 验收

```bash
uv run ruff check .    # 归零
uv run pytest          # 全绿
```

| 项 | 方式 |
|---|---|
| 遮蔽语义 | `test_server_lib` 用例 + 手测：启用组后同 key 命中组数据、非同 key 正常 base |
| 启动即冻结 | 服务运行中 enable/disable/顶替/组数据增删改，命中行为均不变化；重启后按当时启用态装载 |
| 内存收紧 | 休眠组零装载，`test_server_lib` 组路径零 DB 断言 + 手测多组存在时内存仅 base + 单组 |

## 13. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-04 | ① schema v6 + TestGroupMixin + api_data.group_id + 过滤修正 + 测试 | ruff 0 错误；pytest 163 passed / 1 skipped | commit a804e46 |
| 2026-04 | ② 匹配层：双层 map + _resolve_meta 遮蔽解析 + 测试 | ruff 0 错误；pytest 172 passed / 1 skipped | commit a3346d3 |
| 2026-04 | ③ Qt bridge /test_group/* 8 端点（含参数类型 + QT_BRIDGE.md 登记） | ruff 0 错误；pytest 172 passed / 1 skipped | commit 3de1ab3 |
| 2026-04 | ②' 匹配层返工「启动即冻结」：单组快照 + 组路径零 DB + 测试改写 | —— 待验收 | 未提交 |

## 14. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| 2026-04 | `api_data.group_id` 落地为 `TEXT NOT NULL DEFAULT ''`（非裸 TEXT） | 对齐全表既有列约定；`''` 空哨兵避免 NULL 分支（`IS NULL`/`= ''` 两套口径），查询与行映射零特判 |
| 2026-04 | group_map 从「全组装载 + 每请求动态启用」返工为「启用组单份快照，启动即冻结」 | 全组装载内存随组总量线性膨胀（组条目为大 response 副本）；每请求动态读启用态使请求间行为不可预测；冻结版内存 = base + 单组、请求路径组侧零 DB、可预测性最强 |
| 2026-04 | `test_group` 表补 `operator` 列（§3 极简表未列） | §4.1 `insert_test_group(record)` 本就约定写入 operator；与 api_data/static_data/api_response_variants 三表 operator 列惯例一致 |
| 2026-04 | `get_test_group` 的 items 经 `_fetch_group_items` hook 注入 | 复用 `_fetch_variants` 既有解耦先例，避免 TestGroupMixin 对 ApiDataMixin 的隐式依赖 |
