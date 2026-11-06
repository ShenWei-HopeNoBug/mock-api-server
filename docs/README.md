# 文档地图

> 本目录为项目文档总目录，按语义分五类归置；每个子目录自带索引/约定。
> 根目录仅保留门面文件：`README.md` / `CHANGELOG.md` / `LICENSE` / `AGENTS.md`。

## plans/ — 方案与实施文档存档

迭代方案、重构计划、任务拆解等**过程性文档**，按版本（`v0_x_x/`）> 功能域归置。
索引与归置约定见 [plans/README.md](plans/README.md)。

## rules/ — 规则规范

改动代码与提交前必读的**约束性规范**，按主题分子目录，文档统一全大写+下划线命名。

| 文档 | 说明 |
|---|---|
| [code/CODE_RULES](rules/code/CODE_RULES.md) | 代码规范（注释/类型/Qt 约定/命名风格） |
| [git/COMMIT_MESSAGE](rules/git/COMMIT_MESSAGE.md) | git 提交规范（Conventional Commits） |

## reference/ — 现行参考

现行实现说明、协议、架构类**持久参考文档**，SCREAMING_SNAKE_CASE 命名。

| 文档 | 说明 |
|---|---|
| [QT_BRIDGE](reference/QT_BRIDGE.md) | Qt Bridge 桥接协议分层说明（现行约定） |

> 注：`docs/plans/v0_1_3/static-file-handler-method-map.md` 亦属实现说明类，
> 随版本存档冻结保留原位，且已滞后于现行实现。

## reports/ — 评审/排查/审计台账

结论性报告类文档，SCREAMING_SNAKE_CASE 命名。

| 文档 | 说明 |
|---|---|
| [PROJECT_REVIEW_REPORT](reports/PROJECT_REVIEW_REPORT.md) | 项目评审报告与复查记录（问题台账） |

## discussions/ — 思维碰撞记录

探索性方案讨论、竞品分析、方向推演的**记录性文档**，不承诺实施；
SCREAMING_SNAKE_CASE + `_DISCUSSION` 后缀命名。索引与约定见 [discussions/README.md](discussions/README.md)。

| 文档 | 说明 |
|---|---|
| [PRODUCT_DIRECTION_DISCUSSION](discussions/PRODUCT_DIRECTION_DISCUSSION.md) | 产品定位、业界方案对比与迭代方向讨论记录 |
| [TEST_GROUP_DESIGN_DISCUSSION](discussions/TEST_GROUP_DESIGN_DISCUSSION.md) | 测试组（测试任务）概念与 Playwright 编排方案讨论记录 |

## 归置约定

- 新增**过程性方案** → `plans/`（版本 > 功能域，`*-plan.md`，kebab-case，约定见 plans/README）；
- 新增**约束性规范** → `rules/`（主题子目录，SCREAMING_SNAKE_CASE）；
- 新增**现行实现/协议参考** → `reference/`（SCREAMING_SNAKE_CASE）；
- 新增**评审/排查/审计报告** → `reports/`（SCREAMING_SNAKE_CASE）；
- 新增**思维碰撞/方案讨论记录** → `discussions/`（SCREAMING_SNAKE_CASE + `_DISCUSSION` 后缀，约定见 discussions/README）；
  界限：reports 记对现状的评审结论/问题台账，discussions 记对未来的探索与取舍推理；
- 新类别先在本文件登记再建子目录；
- `reports/` 为快照类台账：不改写既有报告内容，问题处理进展以文末新开「处理进展：日期」小节追加；
- 文档变更按 `rules/git/COMMIT_MESSAGE.md` 以 `docs:` 类型提交。
