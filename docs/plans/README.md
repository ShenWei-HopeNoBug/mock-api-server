# 方案文档地图

> 本目录为项目方案与实施文档存档，按 版本目录（`v0_x_x/`）与 功能域 两级归置。
> 上层总地图见 [docs/README.md](../README.md)。
> 约定：每篇为唯一权威方案，偏离修正以增量章节追加、不改正文；
> 跨方案的后续变更单开增量文档（`*-changes.md`）。
>
## v0_1_5/

当前版本工作目录，按功能域分设子目录。

### bugfix/

评审「§8 明确的 bug」逐项修复方案存档。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [download-log-success-flag-plan](v0_1_5/bugfix/download-log-success-flag-plan.md) | `lib/download_lib.py` | 下载失败日志 `success:True` 修正 + 日志块收敛 + `.part` 原子写 + compress 拆 try，单 commit | 已实施 |
| [schema-migration-transaction-plan](v0_1_5/bugfix/schema-migration-transaction-plan.md) | `lib/db/*` | 迁移包事务 + ALTER 幂等化（`_column_exists` 守卫），含 v≤2 老库预建表撞列修复，单 commit | 待实施 |
| [mitmproxy-start-failure-running-plan](v0_1_5/bugfix/mitmproxy-start-failure-running-plan.md) | `qt_win/app.py` / `module/asyncio_mitmproxy_server.py` | ready/死亡双通道轮询 + 失败 terminate 清理 + 异常兜底防 START_WAIT 卡死，单 commit | 已实施 |
| [process-daemon-true-plan](v0_1_5/bugfix/process-daemon-true-plan.md) | `qt_win/app.py` / `module/*` 三处 Process / `CODE_RULES.md` | 三处子进程补 `daemon=True` 落实规则 + daemon 禁孙进程约束写清，单 commit | 已实施 |
| [port-dual-address-check-plan](v0_1_5/bugfix/port-dual-address-check-plan.md) | `lib/utils_lib.py` / `qt_win/app.py` 三处 / `module/app_server.py` | 端口探测精确匹配漏 127.0.0.1 占坑（回环静默劫持）→ `is_local_port_occupied` 通配+回环双地址族单扫描，app_server 顺手统一，单 commit | 已实施 |

### cleanup/

死代码清理：backup_lib/file_lib/hash_lib 删除、`BACKUP_DIR` 摘除、`white_` 命名修正与散件清理。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [dead-code-cleanup-plan](v0_1_5/cleanup/dead-code-cleanup-plan.md) | `lib/` 死代码 / `config/work_file.py` / 命名修正 | 三文件删除 + BACKUP_DIR 摘除 + 命名与散件，单 commit | 待实施 |

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
| [pytest-baseline-plan](v0_1_5/engineering/pytest-baseline-plan.md) | 新增 `tests/`（镜像源码结构）/ `pyproject.toml` / `AGENTS.md` | 测试基线：基建 + 首批 ~90 例（T1 纯逻辑/T2 DB/T3 边界），不含 CI，两 commit 拆分 | 已实施 |

### logging/

日志统一：分域 logger、error_catch 堆栈、print 迁移、-w 打包态防御。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [logging-unification-plan](v0_1_5/logging/logging-unification-plan.md) | `lib/logger_lib` / `decorate` / 运行时 print | 基建加固 + 全量迁移，两 commit 拆分 | 已完成 |
| [multiprocess-logging-queue-plan](v0_1_5/logging/multiprocess-logging-queue-plan.md) | `lib/logger_lib` 重构 / 四 spawn 点 + 子进程入口 / `main.py` / `_cleanup_in_thread` | 多进程共写 app.log 轮转死锁 → QueueHandler + QueueListener 单写进程，格式加 processName，单 commit | 已实施 |

### pyside6/

Qt 客户端升级：PyQt5（QtWebEngine 5.15.2 / Chromium 83）→ PySide6（Qt 6.10 / Chromium 134）。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [pyside6-migration-plan](v0_1_5/pyside6/pyside6-migration-plan.md) | Qt 客户端全量 | 依赖换绑 + 17 文件手改 + 8 个 win_ui.py 重生成，含回归矩阵与回滚策略 | 待实施 |

### qt-bridge/

Qt Bridge 协议信封与分发层统一：信封 `status_code` 单层收敛（DB 删 `success`、MCP 边界派生）、`BridgeDispatcher` 分发器抽离、`BizError` 业务异常；修复前端失败弹成功 bug。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [qt-bridge-refactor-plan](v0_1_5/qt-bridge/qt-bridge-refactor-plan.md) | `lib/bridge_lib.py` / `lib/db/*` / `module/mcp_server` / `qt_win` 两弹窗 / 前端两文件 | 两阶段实施（信封收敛 → 分发层抽离），含风险与验收 | 待实施 |
| [bridge-dispatcher-worker-queue-plan](v0_1_5/qt-bridge/bridge-dispatcher-worker-queue-plan.md) | `lib/bridge_lib.py` / `qt_win` 两弹窗 / `QT_BRIDGE.md` | 无界 thread-per-message → 单 worker FIFO 队列（有界 512、shutdown 排空、回包守卫），refactor §5.5 TODO 收口，单 commit | 已实施 |

### refactor/

结构重构：在不改变外部行为的前提下收敛内部组织。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [static-asset-downloader-plan](v0_1_5/refactor/static-asset-downloader-plan.md) | `lib/download_lib.py` | 下载执行簇封装 `StaticAssetDownloader`（实例化类、session 注入留点），薄入口兼容 + 单 commit | 待实施 |

### security/

安全面收敛：app_server 收 `127.0.0.1`、`/system/shutdown` POST + 回环校验、LAN 暴露面文档。

| 文档 | 范围 | 说明 | 状态 |
|---|---|---|---|
| [security-hardening-plan](v0_1_5/security/security-hardening-plan.md) | `module/app_server` / `module/mock_server` / `lib/server_lib` / `qt_win/app.py` / `README.md` | 绑定收敛最小集 + shutdown 加固，单 commit | 待实施 |

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
