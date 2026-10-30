# 文档地图

> 本目录为项目方案文档存档，按功能域 / 版本分子目录归置。
> 约定：每篇为唯一权威方案，偏离修正以增量章节追加、不改正文；
> 跨方案的后续变更单开增量文档（`*-changes.md`）。
>
## v0_1_5/

当前版本工作目录，按功能域分设子目录。

### dependency/

依赖管理整改：`requirements.txt` 单源化 → uv 迁移两步走。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [dependency-management-plan](v0_1_5/dependency/dependency-management-plan.md) | 全项目依赖配置 | Step 1 requirements.txt 单源化（`5b4dc12`）；Step 2 uv + pyproject.toml 迁移（`fc26535`） | 已完成 |

### engineering/

工程文件补齐：`.gitignore` 重写、LICENSE、CHANGELOG、ruff 配置、editorconfig 等。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [engineering-files-plan](v0_1_5/engineering/engineering-files-plan.md) | 仓库工程文件 | 9 项改动 + lint 基线清理，两 commit 拆分 | 已完成 |

### logging/

日志统一：分域 logger、error_catch 堆栈、print 迁移、-w 打包态防御。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [logging-unification-plan](v0_1_5/logging/logging-unification-plan.md) | `lib/logger_lib` / `decorate` / 运行时 print | 基建加固 + 全量迁移，两 commit 拆分 | 已完成 |

## 历史方案存档

### v0_1_3/

| 文档 | 说明 | 状态 |
|---|---|---|
| [static-file-handler-method-map](v0_1_3/static-file-handler-method-map.md) | StaticFileHandler 方法职责图（direct / throttled 双路径、Range / 缓存协议细节） | 现行实现说明 |

### v0_1_0/

SQLite 重构（JSON 文件存储 → `mock.db`）方案与任务拆解存档。

| 文档 | 说明 | 状态 |
|---|---|---|
| [sqlite-refactor-plan](v0_1_0/sqlite-refactor-plan.md) | 总体方案：表设计、MockDB 数据访问层、迁移策略 | 已落地 |
| [task/README](v0_1_0/task/README.md) | 原子子任务地图（task-01 ~ task-10）、实施顺序与依赖关系 | 已落地 |
| [task-01 ~ task-10](v0_1_0/task/) | 各子任务执行文档（自包含，按 task/README 顺序执行） | 已落地 |

## 新文档归置约定

- 新功能方案按功能域入对应子目录；新功能域先在本文件登记再建目录。
- 文件名带功能前缀（如 `mock-server-*.md`），与目录同名属预期，便于全文检索识别。
- 跨方案变更单开 `*-changes.md` 增量文档，不改正文。
- plan 文档除实施方案本身外，须含「实施记录」「方案修正」栏目，记录实际落地情况与偏离修正（增量章节追加，不改正文）。
- 文档方案的落地执行不自动 git commit，由人确认后提交。
- 版本存档目录（`v0_x_x/`）为历史冻结内容，不再变更；现行方案以功能域目录为准。
