# 子进程 daemon=True 规则对齐方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「复查记录：2026-11-04」🆕 新发现问题 #3；`docs/rules/code/CODE_RULES.md:32`；AGENTS.md 红线
> 状态：已实施（2026-11-05）
> 范围：`qt_win/app.py`、`module/asyncio_mitmproxy_server.py`、`module/mcp_server.py`、`docs/rules/code/CODE_RULES.md`

## 1. 背景

规则与代码矛盾：`CODE_RULES.md:32` 与 AGENTS.md 红线均要求 `multiprocessing.Process` 必须 `daemon=True`，但 4 处 `Process` 仅 `app_server.py:81` 落实，mitmproxy（`asyncio_mitmproxy_server.py:95`）、mock_server（`app.py:739`）、mcp_server（`mcp_server.py:707`）三处未设。

**机制**：解释器正常退出时 `multiprocessing.util._exit_function` 对 `daemon` 子进程先 `terminate()`，再对**所有**存活子进程 `join()`——**无超时**。因此「子进程存活到 atexit」时：daemon → terminate 秒回；非 daemon → 无限挂死（窗口关了 exe 残留，下次启动撞端口占用）。

各子进程优雅停止链与「存活到 atexit」的场景矩阵：

| 子进程 | 优雅停止链 |
|---|---|
| mitmproxy | `stop_event` → watcher → `master.shutdown()` → `done()` 抓包缓冲写 SQLite |
| mock_server | POST `/system/shutdown` + `/ping` 轮询 + `_terminate_mock_process` 兜底 |
| mcp_server | `stop_event` → `_before_shutdown`（关 DB）→ uvicorn `should_exit` |
| app_server | POST `/system/shutdown` → `shutdown_local_server`（已 daemon=True） |

| 场景 | daemon=False（现状） | daemon=True |
|---|---|---|
| 正常关窗 | 无差别（清理流程先杀光） | 无差别 |
| 清理失败/子进程拒绝停止 | atexit join 挂死 → 8s 看门狗 `os._exit` 兜底 → 子进程孤儿 | atexit terminate，无孤儿 |
| 异常退出绕开 `_cleanup_in_thread`（窗口循环前异常/Qt 崩溃/解释器错误） | **atexit join 无限挂死，此路径无看门狗 → exe 永久残留** | terminate 干净退出（差异最大场景） |
| 外部强杀主进程（任务管理器/TaskKill） | 孤儿 | **同样孤儿**（daemon 只在正常退出生效，救不了强杀） |

**"保活刷数据"取舍证伪**：非 daemon 的 atexit join 被期待给 mitmproxy `done()` 刷盘让路——但优雅刷盘已由 `stop_event`+`join(30)` 显式覆盖（正常关窗路径）；atexit join 只在清理被绕过的异常路径有意义，而那些路径上它更可能是无限挂死而非等到数据。

## 2. 决策

| 项 | 决定 |
|---|---|
| 对齐方向 | 三处 `Process` 补 `daemon=True` 落实规则（不改规则） |
| daemon 约束写清 | 规则处补注：daemon 进程禁孙进程（`AssertionError: daemonic processes are not allowed to have children`），现状无违反（Flask 未开 reloader、uvicorn 单进程、mitmproxy 常规代理模式），后续启用 reloader/多 worker/wireguard 模式须先改回 |
| 实施方式 | 当前分支单 commit，不自动提交 |

## 3. 改动清单

### 3.1 `module/asyncio_mitmproxy_server.py`（:95）

```python
mitmproxy_process = Process(
  target=run_mitmproxy, args=(share_dict, ready_event, stop_event),
  name='mitmproxy', daemon=True,
)
```

（顺带补 `name`，与 mock/mcp/app_server 的 `name=` 约定对齐，便于排查）

### 3.2 `qt_win/app.py`（:739）

```python
server_process = Process(
  target=server_process_start,
  args=(server_config,),
  name='mock_server',
  daemon=True,
)
```

### 3.3 `module/mcp_server.py`（:707）

```python
mcp_process = Process(target=run_mcp_server, args=(config, stop_event), name='mcp_server', daemon=True)
```

### 3.4 `docs/rules/code/CODE_RULES.md`（:32）

规则行补 daemon 约束说明（禁孙进程及触发条件），保留原有"退出挂死"理由。

## 4. 影响面

| 项 | 说明 |
|---|---|
| 正常路径 | 零行为变化（优雅停止链不经过 atexit 语义） |
| 异常路径 | 「存活到 atexit」从"挂死/孤儿"收敛为"terminate 干净退出" |
| 孙进程约束 | 现状无违反；规则注释固化防止未来误开 reloader |
| 强杀孤儿 | 不变（Job Objects 才可解，超出本项） |
| 打包 | PyInstaller spawn 机制与 daemon 标志无关，无影响 |

## 5. 行为等价与验收

| 场景 | 构造 | 预期 |
|---|---|---|
| 三服务正常启停 | 各按钮启动→使用→停止 | 行为不变 |
| 服务运行中关窗 | 启动 mitmproxy/mock/mcp 后关窗 | 清理流程正常杀掉，无残留 |
| 异常退出 | 模拟绕过 `_cleanup_in_thread` 的退出（如启动后从外部向主进程发 WM_CLOSE 之外的路径/或临时脚本验证 spawn+daemon 语义） | 子进程不残留 |

```bash
uv run ruff check .   # 保持归零
```

## 6. 明确不做

- 规则本身修改（保留 `daemon=True` 要求，仅补约束说明）；
- Windows Job Object 绑子进程（解外部强杀孤儿，独立立项）；
- `create_thread` 非 daemon 线程（报告 §9 独立问题）；
- 各子进程优雅停止链逻辑任何改动；
- `app_server.py`（已 daemon=True，不动）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-05 | 按 §3 全部实施 | `ruff` 归零；daemon 语义实测：spawn `sleep(60)` daemon 子进程后主进程正常退出，atexit terminate 生效（子进程 PID 不存在）；mitmproxy 顺带补 `name='mitmproxy'` 对齐其余 Process 命名约定 | 实施前已核实无孙进程 spawn（mock 无 reloader、uvicorn 单进程、mitmproxy 常规代理模式） |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| - | - | - |
