# 测试组（测试任务）设计讨论报告

> 讨论日期：2026-11-07
> 参与者：项目作者 × Devin
> 性质：思维碰撞记录，非实施承诺；若立项实施，转 `plans/vX_X_X/test-group/` 起正式方案

## 1. 背景与动机

当前要做"针对某个测试任务启用一组特定接口"的操作，只能手动或在 MCP 里逐条启用/禁用、甚至临时创建数据，流程繁琐。同时状态机类 case（进行中/成功/失败等合成 status）需要确定性的变体控制能力。

目标概念：**测试组（测试任务）** = 一组 mock 接口数据（含变体）的命名集合 + 测试步骤定义 + 运行记录，可一键启用/停用。

## 2. 核心概念与匹配语义决策

### 2.1 决策总览

| 决策点 | 结论 |
|---|---|
| 组数据定位 | 第 4 优先级层：`TEST_GROUP(启用组) > USER > MCP > MITMPROXY` |
| 覆盖模式 | **遮蔽模式**：组数据仅在 key 冲突时赢，组外接口正常响应 |
| 启用模型 | **单组启用**：`enabled` 全局至多一行，启用新组原子顶替旧组 |
| 生效机制 | 请求时判定 active group → **切组零重启**；编辑组数据仍走重启生效 |
| 数据归属 | 新增 `TEST_GROUP` type + `api_data.group_id`；已有数据**拷贝式**入组 |

### 2.2 第 4 优先级层（机制复用）

现有 `create_api_map` 按 MITMPROXY → MCP → USER 顺序加载、同 key 后者覆盖前者。测试组是这个"加载顺序覆盖"语义从**类型维度到组维度**的延伸——概念上不引入新机制，数据类型优先级叙事变成一行话：

```
TEST_GROUP(启用组) > USER > MCP > MITMPROXY
```

### 2.3 遮蔽模式（已决策）

组启用时，组数据只在 key 冲突时遮蔽底层数据，组外接口照常响应。

- **理由**：主用例是"正常应用里注入一个异常场景"（bug 复现、状态覆盖），页面其余接口需要正常工作；
- 备选的"纯净模式"（组启用期间仅组内数据响应，其余 404）隔离彻底但要求组内录全页面所有接口，实用度低，留作组级 flag 后补；
- 实现上是"先查组 map，miss 落 base map"的自然结果。

### 2.4 单组启用（已决策）

`enabled` 全局至多一行（启用新组 = 一个事务内 `UPDATE ... SET enabled=0; UPDATE ... SET enabled=1 WHERE id=?` 原子顶替）。

- **收益一**：同 key 冲突只可能来自唯一启用组，多组优先级消解、UI 冲突提示全不需要；
- **收益二**：遮蔽模型下组的启用**从不碰**底层数据的 enabled 标志，"停用组"与"组从未启用"在匹配层完全等价——天然无损还原，不需要"快照原 enable 状态再恢复"那套机制；
- 语义：`enable_test_group` 即"原子切换"，MCP 工具描述写清楚即可。

### 2.5 切组零重启的机制（关键设计点）

热更新（改 mock 数据实时生效）可以延后，因为**高频操作是"切组"不是"改组数据"**：

- 数据结构分两层：`base_map`（维持现状）+ `group_map`（所有 TEST_GROUP 数据按 `group_id` 组织，无论组是否启用都加载，entry 带 `group_id`）；
- 请求处理时先查 `group_map`（过滤 `entry.group_id == active_group_id`），miss 再查 `base_map`；
- 组开关是运行时 flag：mock 子进程请求时 `SELECT id FROM test_group WHERE enabled=1`（SQLite 索引读微秒级，dev 场景足够；或加短 TTL 缓存），零 IPC；
- 服务重启时从 DB 恢复启用态，启用状态天然可持久化；
- 欠账："编辑组内数据内容"仍需重启生效，等热更新立项一起解决。

### 2.6 边界与已知限制

- **key 一致性前提**：遮蔽要求 url/method/params/content_type 完全一致（同 request_key+response_key）。组内改 key 字段会悄悄从"覆盖"变"新增"——非 bug 是机制必然，建议组数据编辑 UI 上提示"修改 key 字段将使该条变为新增接口而非覆盖"；
- **表达不了"接口应 404"**：遮蔽只能覆盖不能消除。变通：建错误响应变体顶上；根治等自定义状态码能力（见 PRODUCT_DIRECTION 短板清单）。

## 3. 数据归属语义

- `TEST_GROUP` 作为第 4 类数据来源 type：与现有"数据从哪来"（抓包/手动/Agent）语义一脉相承；加载规则变"base_map 排除 TEST_GROUP、group_map 只装 TEST_GROUP"，一个 type 值完成两套 map 切分；
- `api_data` 加 `group_id`（nullable，仅 TEST_GROUP 行有值）标归属——type 标"是什么"，group_id 标"属于谁"；join table 不必要（单组启用下一条组数据只属于一个组）；
- **拷贝式包装**："把已有接口加进组" = 复制 api 行 → `type=TEST_GROUP`、`group_id=X`、route/params 不变。组内可自由改、不污染原始数据、删组连带清理；原始录制后续更新不同步——对测试"数据稳定可复现"恰是要的特性；
- 从 MITMPROXY 数据拷入时原 type 丢失，需要追溯可令 `operator` 记 `copied-from-<原type>`（可选）；
- **变体零成本复用**：变体按 `api_data_id` 关联，组数据建变体无机制改动；拷贝时可选择连带变体一起拷；
- **存量查询过滤点**：`get_mock_api_data_list` 三个类型查询须排除 TEST_GROUP；`list_mock_apis` 的 `api_type` 枚举文档加值；GUI 主数据列表默认隐藏组数据或加 group 徽标区分。

## 4. 数据模型草案

```sql
-- api_data 变更
ALTER TABLE api_data ADD COLUMN group_id TEXT;  -- 仅 type=TEST_GROUP 行有值

CREATE TABLE test_group (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  context TEXT NOT NULL DEFAULT '',   -- 任务级提示词前言（模板，支持 {device_id} 占位）
  base_url TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 0, -- 全局至多一行为 1
  priority INTEGER NOT NULL DEFAULT 0,-- 为多组启用预留（v1 单组）
  created_at / updated_at ...
);

CREATE TABLE test_step (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  process TEXT NOT NULL DEFAULT '',   -- 驱动 playwright 的提示词
  target TEXT NOT NULL DEFAULT '',    -- 验收预期提示词
  created_at / updated_at ...
);

CREATE TABLE test_run (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL,
  device_id TEXT NOT NULL DEFAULT '', -- run 级变体隔离标识
  status TEXT NOT NULL DEFAULT '',
  started_at / finished_at ...
);

CREATE TABLE test_run_step (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_seq INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT '',
  agent_note TEXT NOT NULL DEFAULT '',
  screenshot_path TEXT NOT NULL DEFAULT '',
  -- 建议存 process/target 文本快照：步骤后来改了，历史 run 仍可追溯
);
```

## 5. 组内 item 的变体模式

组内每个 item 两种模式：

- `pin`：固定到指定变体（测确定性 case，如"status=failed 的 UI"）；pin 目标变体被禁用时兜底落"该 item 首个启用变体"并记 warning；
- `sequence`：走现有 Device-Id 轮播（测流程性 case，如"第 1 次 pending → 第 2 次 success"）。

## 6. MCP 工具面草案

- 组 CRUD + `enable_test_group` / `disable_test_group`；
- `list_test_tasks` / `get_test_task(id)` → 返回 `{context + 有序步骤[{seq, process, target}]}`（context 中 `{device_id}` 等占位符在 run 时注入）；
- `begin_test_run(task_id)` → `{run_id, device_id}`，**顺便自动启用该测试组**；
- `report_step_result(run_id, step_seq, status, note, screenshot_path?)`；
- `finish_test_run(run_id, status, summary)` → **自动恢复组启用前状态**。

`begin/finish` 把"布防 → 执行 → 收防"闭成环：Agent 一次会话完成切场景、跑步骤、写回结果、还原环境。工具描述与返回结构应把**执行协议**写清楚（按 seq 顺序执行、每步结束调 report_step_result、全部结束调 finish_test_run）——当成对 Agent 的 API 契约设计，而非给人看的文档。

## 7. Playwright 步骤编排

### 7.1 步骤模型

- 步骤 = `process`（驱动 playwright 的提示词）+ `target`（验收预期提示词）+ `seq`；
- 任务级 `context` 字段：抽离步骤间重复的环境信息（被测 base URL、登录前置、mock 标识约定），支持 `{device_id}` 占位符——步骤只写领域动作，环境接线由工具在返回时组合；
- v1 不做 Given-When-Then 结构化 schema：Agent 吃自然语言足够，过度建模限制表达。

### 7.2 执行边界（重要）

工具做**测试定义的持久化 + mock 控制面**，执行完全交给外部 Agent + playwright-mcp：

- 不做内嵌 LLM runtime（API key 管理/成本/重试全是新坑，会把项目拖成大而全）；
- 保持 agent 无关性：Devin、Claude Code、Cursor 谁来执行都行；
- 判断标准：凡是需要 LLM 在场的环节不进本仓库。

### 7.3 device_id 与浏览器场景

变体轮播依赖 `Mock-Server-Device-Id` 请求头，但 playwright-mcp 驱动真实浏览器，前端代码不会发这个头。**配套小改动：mock 服务同时认 cookie 或 query 参数**（如 `__mock_did`），playwright-mcp 设 cookie/拼 URL 即可。

收益：`begin_test_run` 每次发新 UUID → 每次 run 的变体序列天然隔离、可重放——**会话级 stateful mock sequence** 业界几乎没有，是可写进 README 的卖点。

### 7.4 target 写法约定

自然语言断言的最大风险是漂移。在步骤编辑 UI 与 MCP 工具描述里引导写成**可观察的断言要点**（"列表第一项显示红色'支付失败'标签"而非"检查页面正常"），最好能让 Agent 逐条回报——不花代码成本显著提升可靠性。

### 7.5 远期可选

把 Agent 成功跑过的工具调用序列固化回放成 `.spec.ts`——先用自然语言探路，探通了转代码进 CI。phase 3 以后的事。

## 8. 落地节奏与遗留问题

### 建议节奏

- schema **一次迁移到位**（5 处变更都很薄，表先立着不影响什么）；
- 功能三刀：
  1. 测试组本体：表结构 + GUI 管理 + `group_map` 双层匹配 + 运行时开关；
  2. MCP 工具面：组 CRUD + enable/disable；
  3. 步骤与运行：step 编辑 + run/step 记录 + begin/finish 布防闭环。

### 遗留问题清单

| 项 | 说明 |
|---|---|
| 多组启用 | v1 单组；`priority` 字段已预留，未来启用需补冲突消解与 UI 提示 |
| 纯净模式 | 组级 flag 后补 |
| 断言漂移 | target 写法约定 + 运行历史观察，必要时再结构化 |
| 执行协议 | `get_test_task`/`begin_test_run` 返回结构与工具描述需提示词工程打磨，保证不同 Agent 稳定理解流程约定 |
| 遮蔽表达不了 404 | 等自定义状态码能力根治 |
| 编辑组数据需重启 | 归热更新立项 |

## 9. 关联文档

- [PRODUCT_DIRECTION_DISCUSSION](PRODUCT_DIRECTION_DISCUSSION.md) —— 本方案的上位讨论（定位、竞品、迭代方向）
