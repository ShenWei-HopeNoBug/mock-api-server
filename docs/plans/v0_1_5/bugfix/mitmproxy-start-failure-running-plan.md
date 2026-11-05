# mitmproxy 启动失败误报 RUNNING 修复方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「复查记录：2026-11-04」🆕 新发现问题 #1（联动 #2）
> 状态：已实施（2026-11-05）
> 范围：`qt_win/app.py`、`module/asyncio_mitmproxy_server.py`

## 1. 背景

`start_catch_server`（`qt_win/app.py:594-597`）对 `ready_event.wait(timeout=10)` 的结果不区分：超时仅记 warning 后无条件 `emit('RUNNING')`。

`ready_event` 唯一置位点是 `RequestRecorder.running()` 钩子（`request_catch.py:79-81`）。已核实 mitmproxy 12.2.3 `Master.run()` 时序：`setup_servers()`（绑定端口）→ `errorcheck` → `running()`——**`running` 只在端口真正监听后触发**。因此三类「running 之前死亡」的故障全部误报 RUNNING：

| 死法 | 路径 | 进程结局 |
|---|---|---|
| 端口绑定失败 | `setup_servers` 报错 → `errorcheck` → `sys.exit(1)` | exitcode=1 |
| 配置损坏 | `RequestRecorder.__init__` → `load_mitmproxy_config` 裸 `json.loads`（`request_catch.py:87-88`），发生在 `master.run()` 之前 | 异常退出 |
| 启动异常 | `Event()`/`Process.start()` 抛错 | 线程死，`START_WAIT` 卡死（`create_thread` 无异常兜底，`decorate.py:97-103`） |

放大因素：预检 `check_local_connection('0.0.0.0')`（`qt_win/app.py:566`）漏检 `127.0.0.1`-only 占用（报告问题 #2），使「预检放行 → 子进程 bind 失败 → 误报 RUNNING」成为真实可达路径；预检与 bind 之间天然存在 TOCTOU 窗口，预检无法根除此问题。

误报代价：假 RUNNING 下端口输入框、抓包配置/数据编辑菜单、mock 与 MCP 服务按钮全部禁用（`app.py:457-469`）；用户点「停止抓包服务」走 `_stop_catch_server` 的 `is_alive` 兜底静默回 READY，全程无错误提示。

## 2. 决策

| 项 | 决定 |
|---|---|
| 超时语义 | 双通道轮询：`ready_event` 置位 或 子进程死亡，先到先判；进程早夭秒回不再等满 10s（Windows 下 `multiprocessing.Event` 不支持 wait-multiple，0.2s 步进轮询） |
| alive 但超时未 ready | 按失败处理并 `terminate`：正常 bind 远低于 10s，半死进程留着会成「UI READY 但代理在跑」的孤儿 |
| 失败呈现 | `message_dialog_signal` 弹窗（沿用端口占用既有模式）+ `emit('READY')`；子进程死亡记 `exitcode` |
| 异常兜底 | `start_catch_server` 拆分为线程入口 + `_start_catch_server` 同步实现，入口包 try/except，任何异常都落到 READY（防 START_WAIT 卡死） |
| 子进程侧 | `run_mitmproxy` 补异常日志——running 之前的崩溃在 `-w` 打包下 `sys.stderr=None`，multiprocessing 打印的栈蒸发，父进程只有 exitcode |
| 实施方式 | 当前分支单 commit，不自动提交 |

## 3. 改动清单

### 3.1 `qt_win/app.py` — 新增 `_terminate_mitmproxy_process` 辅助

与 `_terminate_mock_process`（`app.py:670-677`）对称，顺带清理三个引用：

```python
  # 强制终止 mitmproxy 子进程并清理引用
  def _terminate_mitmproxy_process(self, reason: str, timeout: int = 3) -> None:
    if self.mitmproxy_process is None:
      return
    if self.mitmproxy_process.is_alive():
      APP_LOGGER.warning(f'{reason}，强制终止子进程！port={self.catch_server_port}')
      self.mitmproxy_process.terminate()
      self.mitmproxy_process.join(timeout=timeout)
    self.mitmproxy_process = None
    self.mitmproxy_stop_event = None
    self.mitmproxy_ready_event = None
```

### 3.2 `qt_win/app.py` — `start_catch_server` 拆分与等待逻辑重写

入口拆分（对齐 `stop_catch_server` → `_stop_catch_server` 现有命名约定）：

```python
  # 启动抓包服务
  @create_thread
  def start_catch_server(self) -> None:
    try:
      self._start_catch_server()
    except Exception as e:
      APP_LOGGER.error(f'启动抓包服务异常：{e}', exc_info=True)
      self._terminate_mitmproxy_process(reason='启动抓包服务异常')
      self.message_dialog_signal.emit('critical', '启动失败', '抓包服务启动异常，请检查日志！')
      self.mitmproxy_server_status_signal.emit('READY')
```

`_start_catch_server` 前半段（alive 跳过 / 端口预检 / config / 两个 Event / `start_mitmproxy`）原样保留，尾部改为：

```python
    self.mitmproxy_process = start_mitmproxy(
      share_dict=mitmproxy_config,
      ready_event=self.mitmproxy_ready_event,
      stop_event=self.mitmproxy_stop_event,
    )
    # 双通道轮询：ready_event 置位或子进程死亡任一先到即结束等待，最多 10 秒
    deadline = time.monotonic() + 10
    ready = False
    while time.monotonic() < deadline:
      if self.mitmproxy_ready_event.wait(timeout=0.2):
        ready = True
        break
      if not self.mitmproxy_process.is_alive():
        break

    if ready:
      self.mitmproxy_server_status_signal.emit('RUNNING')
      return

    # 启动失败：子进程已死 或 超时未就绪（仍 alive 的半死进程须终止防孤儿）
    if not self.mitmproxy_process.is_alive():
      APP_LOGGER.error(f'mitmproxy 子进程启动失败退出，exitcode={self.mitmproxy_process.exitcode}')
      fail_reason = '抓包子进程启动失败已退出'
    else:
      APP_LOGGER.error('mitmproxy 服务启动超时（10s），判定启动失败')
      fail_reason = '抓包服务启动超时'
    self._terminate_mitmproxy_process(reason=f'mitmproxy 启动失败（{fail_reason}）')
    self.message_dialog_signal.emit('critical', '启动失败', f'{fail_reason}，请检查日志！port={self.catch_server_port}')
    self.mitmproxy_server_status_signal.emit('READY')
```

### 3.3 `module/asyncio_mitmproxy_server.py` — 子进程退出原因落盘

```python
  try:
    loop.run_until_complete(mitmproxy_task(...))
  except BaseException as e:
    # SystemExit（端口绑定失败经 errorcheck 退出）与 Exception 一并记录后原样抛出
    CATCH_LOGGER.error(f'mitmproxy 子进程退出：{type(e).__name__} {e}', exc_info=True)
    raise
  finally:
    loop.close()
```

### 3.4 `qt_win/app.py` — `_cleanup_in_thread` mitmproxy 孤儿兜底对齐

现状仅 `mitmproxy_server_status == 'RUNNING'` 一个分支（`app.py:936-938`），START_WAIT 窗口期关窗会漏掉已 spawn 的子进程。补 elif（与 mock/mcp 分支孤儿兜底一致，`app.py:942-945,949-958`）：

```python
    if self.mitmproxy_server_status == 'RUNNING':
      self.cleanup_progress_signal.emit('正在清理抓包服务…')
      self._stop_catch_server()
    elif self.mitmproxy_process is not None and self.mitmproxy_process.is_alive():
      self.cleanup_progress_signal.emit('正在清理抓包服务…')
      self._terminate_mitmproxy_process(reason='退出清理：检测到 mitmproxy 孤儿子进程仍在运行', timeout=5)
```

## 4. 影响面

| 调用方/路径 | 结论 |
|---|---|
| 正常启动（10s 内 ready） | 行为零变化 |
| 端口占用（0.0.0.0 预检拦截） | 行为不变 |
| 子进程早夭（bind 失败/配置损坏） | 假 RUNNING → 快速弹窗 + READY，exitcode 落日志 |
| 超时未 ready（进程 alive） | 假 RUNNING → terminate + 弹窗 + READY |
| `Event()`/`Process.start()` 等异常 | START_WAIT 卡死 → 弹窗 + READY |
| `_stop_catch_server` / `stop_catch_server` | 不改动，`is_alive` 防御仍有效 |
| `_cleanup_in_thread` | 仅加 elif 分支，RUNNING 路径不变 |
| 状态机 | 不新增状态；`mitmproxy_server_status_change` 各分支无需改 |
| 报告问题 #2 | 部分缓解（bind 失败可正确报错）；双地址预检不在本方案 |

## 5. 行为等价与验收

| 场景 | 构造 | 预期 |
|---|---|---|
| 正常启动 | 空闲端口点启动 | RUNNING，代理可用 |
| 0.0.0.0 占用 | 同端口已有监听 | 预检弹窗 + READY（现状） |
| 127.0.0.1-only 占用 | `python -m http.server --bind 127.0.0.1 <port>` | 秒级失败弹窗 + READY（不再误报/等满 10s） |
| 配置损坏 | `{work_dir}/{CONFIG_DIR}/mitmproxy_config.json` 写成非法 JSON | 快速失败弹窗 + READY，日志含子进程退出原因 |
| START_WAIT 期关窗 | 启动后 10s 窗口内关应用 | 子进程被清理不留孤儿 |
| 失败后重启 | 上述任一失败后再次点启动 | 引用已清，可正常重试 |

```bash
uv run ruff check .   # 保持归零
```

## 6. 明确不做

- 端口预检改双地址探测（报告问题 #2，独立立项，参照 `app_server.py:90-92`）；
- RUNNING 后子进程崩溃的存活监控（报告 §9，独立立项）；
- `Process daemon=True` 规则对齐（报告问题 #3，独立立项）；
- `load_mitmproxy_config` 裸 `json.loads` 的损坏回退（配置管理薄弱项，独立立项）；
- `_stop_catch_server` 尾部复用 `_terminate_mitmproxy_process` 的重构（现状逻辑正确，不动）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-05 | 按 §3.1-3.4 全部实施 | `ruff` 归零；临时脚本三场景实测通过：0.0.0.0 占用→DEAD exitcode=1（1.43s）、配置损坏→DEAD exitcode=1（1.42s）、正常启动→READY（1.14s） | 验证用临时脚本未入库；实测发现 Windows 下 `127.0.0.1`-only 占用**不会**导致 mitmproxy `0.0.0.0` bind 失败（Windows SO_REUSEADDR 语义允许重复绑定），该形态为「静默劫持端口」而非崩溃——更凸显问题 #2 双地址预检的必要性，本方案不覆盖 |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| - | - | - |
