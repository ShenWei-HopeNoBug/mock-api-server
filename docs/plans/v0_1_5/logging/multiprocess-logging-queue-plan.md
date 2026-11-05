# 多进程日志单点写盘（QueueHandler + QueueListener）方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「复查记录：2026-11-04」🆕 新发现问题 #4；`lib/logger_lib.py`；`docs/plans/v0_1_5/logging/logging-unification-plan.md`
> 状态：已实施（2026-11-05）
> 范围：`lib/logger_lib.py`（重构）、`main.py`、`qt_win/app.py`、`lib/server_lib.py`、`module/asyncio_mitmproxy_server.py`、`module/mcp_server.py`、`module/app_server.py`、`docs/rules/code/CODE_RULES.md`

## 1. 背景

`FILE_LOGGER_HANDLER` 是模块级单例 `RotatingFileHandler(logs/app.log, 10MB, backup=5)`，在 **import 时创建**。GUI + mitmproxy + mock_server + mcp_server + app_server 五个进程各自 import `logger_lib` → 各持 `app.log` 打开句柄。

**日常并发 append 无碍**：Windows 下 Python `open('a')` 为 FILE_APPEND_DATA 共享写，单条记录 `write()` 基本原子。

**雷在轮转**：`shouldRollover` 用 `seek(0,2)` 读真实 EOF（所有进程都看得到真实大小）；`doRollover` 先关自己句柄、搬移 `.i→.i+1`（成功），再 `os.rename(app.log→app.log.1)`——Windows 下 rename 要求无 delete-share 外的打开句柄，**其他进程正持有** → `PermissionError (WinError 32)`。后果链：

1. `handleError` 在 `-w` 打包态 `sys.stderr=None` → 静默吞掉，该条记录丢；
2. `doRollover` 抛出后 `self.stream` 停在 None → 下一条 emit 重开文件 → 仍 >10MB → 再 rename → 再失败 → 再丢；
3. 每个进程独立踩进同一循环 → **所有进程日志记录永久丢失**，文件无限增长；
4. 每次失败重试前 `.i→.i+1` 搬移已成功 → `.1` 内容被反复覆盖，**历史备份逐次蚕食**；
5. `app.log` 跨 session 累积（append 从不截断），10MB 正常使用迟早到达 → **触发概率低但必然，触发后当 session 日志静默全损**。

## 2. 决策

| 项 | 决定 |
|---|---|
| 方案 | **C：QueueHandler + QueueListener 单写进程**——父进程独占文件/控制台 handler 并起 listener 线程消费 `mp.Queue`；子进程仅持 `QueueHandler` 把 LogRecord 入队 |
| 对比取舍 | A（`app-{pid}.log`）一行改完但文件按 pid 碎裂、排障差；B（per-role 文件）须先解决 spawn 导入期身份注入，且**域排障需跨文件 grep**——"单进程独占文件"与"全域单文件"互斥，只有 C 两全 |
| handler 边界 | **逐域 logger 挂 handler + `propagate=False`**（双端一致），维持"仅 8 个域 logger 写文件"的现有边界，不吃 werkzeug/uvicorn/mitmproxy termlog 等第三方根传播 |
| 子进程 handler | **仅 QueueHandler，不挂 Stream**——dev 态子记录经父进程 listener 的 STREAM 打印一次，统一控制台且不重复 |
| 阻塞语义 | `QueueHandler` 底层 `put_nowait`；`mp.Queue` 无界 → 子进程 emit 永不阻塞 |
| 队列传递 | `mp.Queue` 在父进程 `configure_logging('parent')` 时创建，`Process` args 追加传给子进程入口；**不可走 env/pipe 之外通道**（spawn 传队列是标准姿势） |
| 日志格式 | `LOG_FORMAT` 加 `%(processName)s` 列——四个子进程 `name=` 已齐备（`mitmproxy`/`mock_server`/`mcp_server`/`app_server_process`），父进程显示 `MainProcess`，子记录来源可溯 |
| 子进程配置兜底 | 入口函数首行 `configure_logging('child', q)` 包 try/except：日志初始化失败不拖死服务进程（此时无通道，只能静默继续） |
| 实施方式 | 当前分支单 commit，不自动提交 |

## 3. 改动清单

### 3.1 `lib/logger_lib.py`（重构，~100 行）

- `LOG_FORMAT` 改为 `'%(asctime)s - %(processName)s - %(name)s - %(levelname)s - %(message)s'`；
- **import 期零副作用**：删除模块级 `STREAM_LOGGER_HANDLER`/`FILE_LOGGER_HANDLER` 创建；`setup_logger` 退化为 `setLevel` + 防重复，不挂 handler（8 个域 logger 对象创建不变，外部 import 兼容）；
- 新增 `configure_logging(role: str, queue: Optional[Queue] = None)`：
  - `parent`：建 `mp.Queue` 存入模块全局；建 FILE+STREAM handler；逐域 logger 挂两 handler 且 `propagate=False`；`QueueListener(queue, file_h, stream_h).start()`；
  - `child`：逐域 logger 挂 `QueueHandler(queue)` 且 `propagate=False`；幂等守卫（重复调用直接返回）；
- 新增 `get_log_queue() -> Queue`（供 4 处 spawn 点取参；parent 未 configure 时调用报错）；
- 新增 `shutdown_logging()`：`listener.stop()`（join listener 线程、排空已入队队尾），幂等。

### 3.2 `main.py`

`main()` 最前（建 MainWindow / 任何子进程 spawn 之前）调 `configure_logging('parent')`。

### 3.3 四个 spawn 点（args 追加 `get_log_queue()`）

| spawn 点 | args 现状 → 改后 |
|---|---|
| `module/asyncio_mitmproxy_server.py:95` | `(share_dict, ready_event, stop_event)` → 末尾追加 `log_queue` |
| `qt_win/app.py:739`（mock） | `(server_config,)` → `(server_config, log_queue)` |
| `module/mcp_server.py:707` | `(config, stop_event)` → 末尾追加 `log_queue` |
| `module/app_server.py:77` | `(server_config,)` → `(server_config, log_queue)` |

### 3.4 四个子进程入口（首行配置）

| 入口 | 签名改动 | 首行新增 |
|---|---|---|
| `run_mitmproxy`（`asyncio_mitmproxy_server.py:66`） | `+log_queue` | `try: configure_logging('child', log_queue) / except Exception: pass` |
| `server_process_start`（`lib/server_lib.py:408`） | `+log_queue` | 同上 |
| `run_mcp_server`（`mcp_server.py:693`） | `+log_queue` | 同上 |
| `start_app_server_process`（`app_server.py:62`） | `+log_queue` | 同上 |

### 3.5 `qt_win/app.py` `_cleanup_in_thread`

子进程清理完成后、`os._exit` 看门狗生效前调 `shutdown_logging()`（包 try/except），排空 listener 队尾。

### 3.6 `docs/rules/code/CODE_RULES.md`

新增日志架构规则：文件/控制台 handler 仅父进程持有；**新增 `Process` 必须 args 传 `log_queue` 且入口首行 `configure_logging('child', log_queue)`**；域 logger 之外不挂文件 handler。

## 4. 影响面

| 项 | 说明 |
|---|---|
| 文件写入 | 单写进程，`os.rename` 无竞争者 → 轮转恢复，`app.log.1~.5` 正常生成 |
| 记录外观 | 多一列 `processName`；域 tag 不变；跨进程顺序=到达序（asctime 可回溯） |
| 子进程 import 期日志 | `configure` 前域 logger 无 handler → dev 态走 lastResort stderr 可见，-w 丢；各入口模块级无日志调用，影响≈0 |
| 子进程优雅退出 | `mp.Queue` 每进程注册 Finalize → 退出时 `join_thread` 自动冲刷，队尾不丢 |
| 子进程被强杀 | 在途记录丢（固有）；父进程日志不受影响 |
| 父进程崩溃 | 子进程 `put_nowait` 管道断 → `handleError`（-w 静默丢）；父已死，影响可忽略 |
| dev 控制台 | 子记录经父 STREAM 统一打印，无双写；-w 无 stderr 行为不变 |
| 内存 | `mp.Queue` 无界 + listener 极简消费；listener 卡死的理论风险接受 |
| 调用方兼容 | 8 个域 logger 对象签名不变，全项目 `X_LOGGER.info(...)` 零改动 |

改后 `app.log` 外观：

```
2026-11-05 14:32:07 - mitmproxy - CATCH - INFO - mitmproxy 代理已就绪: 0.0.0.0:8080
2026-11-05 14:32:07 - mitmproxy - DB - INFO - 数据库连接成功: server\data\mock.db
2026-11-05 14:32:08 - mock_server - MOCK - INFO - Mock 服务启动: 127.0.0.1:5050
2026-11-05 14:32:15 - mcp_server - MCP - INFO - MCP 服务已启动: 127.0.0.1:8765
```

## 5. 行为等价与验收

| 场景 | 构造 | 预期 |
|---|---|---|
| 全进程冒烟 | 起 mock+mitmproxy+mcp+app_server，抓包/调用各走一遍 | `app.log` 单文件含各 `processName` 记录 |
| 轮转 | 临时调小 `maxBytes` + 多进程猛写 | rename 成功，无 PermissionError，记录不丢 |
| 突发量 | 子进程写 5000 条 | 全部到达，单进程内有序 |
| 杀单子进程 | `taskkill` 运行中的 mitmproxy | 父进程与其余子进程日志正常续写 |
| 优雅退出尾部 | 停止 mock 服务 | 其退出前最后记录落盘 |
| 旧文件兼容 | 已有 `app.log*` 存在 | 父进程 append 续写，轮转后自然滚动，不迁移 |

```bash
.venv/Scripts/ruff.exe check .   # 保持归零
```

## 6. 明确不做

- werkzeug/uvicorn/mitmproxy termlog 等第三方 logger 仍不入 `app.log`；
- `mp.Queue` 内存背压与 listener 健康监控（接受理论风险）;
- 日志结构化/JSON 化、远端聚合；
- 历史 `app.log*` 文件迁移或截断；
- 各子进程业务日志内容增删（只改传输通道）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-05 | 按 §3 全部实施 | `ruff` 归零；临时脚本实测：spawn 子进程经 `mp.Queue` 投递的 CATCH/DB/APP 域记录全部落盘（`processName=test_child` 可溯）；`maxBytes=2048` 触发轮转 → `.1~.5` 正常生成、无 PermissionError、无 handleError 噪音（旧实现子进程持句柄必败）；`shutdown_logging` 后父进程直写不受影响 | dev 态子记录经父 STREAM 统一打印一次，无双写；四入口 `log_queue` 均为 `Optional` 末位参数，未传则 `configure_logging` 抛 ValueError 被入口 try/except 静默降级 |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| - | - | - |
