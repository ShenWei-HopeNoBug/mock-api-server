# BridgeDispatcher 线程模型收敛：单 worker + FIFO 队列方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「复查记录：2026-11-04」🆕 新发现问题 #5；[qt-bridge-refactor-plan](qt-bridge-refactor-plan.md) §5.5 TODO「无界线程模型待议」（本方案为该 TODO 的收口）
> 状态：待实施
> 范围：`lib/bridge_lib.py`、`qt_win/mitmproxy_data_edit_dialog.py`、`qt_win/download_proxy_config_dialog.py`、`docs/reference/QT_BRIDGE.md`

## 1. 背景

`dispatch` 是 `js2qt_signal` 的槽函数，由 QWebChannel 在 GUI 线程触发；现实现每收到一条消息就 `threading.Thread(target=_dispatch_safe).start()`（`bridge_lib.py:118`）——**无上限、非 daemon、无句柄**。

worker 线程本身是合理设计：两弹窗 handler 全做 SQLite I/O（`MockDBCache`）或配置 I/O（`ConfigFileManager`），跑在 GUI 线程会卡 UI。qt-bridge 重构 §5.1 将原每 handler 一层 `@create_thread` 收敛为 dispatcher 统一起线程，但当时已记录「无界线程模型待议」。

三个缺陷的实际后果：

| 缺陷 | 后果 |
|---|---|
| 无上限 | 前端高频消息（JS bug 死循环等）→ 线程无界增长，每线程 ~1MB 栈 + GIL 争抢；且 spawn ~0.5-1ms 已比 handler 本身贵 |
| 非 daemon | 继承 GUI 线程 `daemon=False` → 退出卡 `threading._shutdown`，靠退出流程 8s `os._exit` 看门狗兜底 |
| 无句柄 | 弹窗关闭时在途 handler 仍在跑；`_send` → `interact_obj.qt2js_signal.emit` 打到已删除 QObject → `RuntimeError`（`_on_cleanup_done` 对两弹窗 `close()+deleteLater()` 是真实路径） |

附带发现：并发执行无顺序保证，而 `MockDB` 全部读写由单连接 `threading.Lock` 串行（`base.py:30`）——**多线程对 DB handler 吞吐零增益**，只引入乱序风险。

实测 handler 耗时（真实库 32 行）：`get_api_count` ~0.00ms、`get_api_list_page(20)` ~0.14ms、LIKE 模糊查询 ~0.01ms、`get_api_detail` ~0.02ms。15 个 handler 无任何网络/重 I/O 路径——即使数据量放大 100 倍，单次也仅一至几毫秒。

## 2. 决策

| 项 | 决定 |
|---|---|
| 线程模型 | **单常驻 worker + FIFO 队列**：`dispatch` 只做非阻塞入队，1 个 daemon worker 顺序消费 |
| 队列 | `queue.Queue(maxsize=512)`（对齐 `dedup_size` 量级）；`put_nowait` + `Full` 时 warn+丢弃——dispatch 跑在 GUI 线程绝不能阻塞；满时被丢 request 前端超时，属可接受有界降级 |
| 顺序语义 | FIFO 确定性顺序（相对现状乱序并发的行为改善；DB 锁本就串行，吞吐无损失） |
| 关闭语义 | `shutdown()`：置 `_closed` 拒收新消息 → 队尾放 poison pill → **已入队消息全部排空**（不丢写操作）后 worker 退出；非阻塞不 join，closeEvent 调用不卡 GUI |
| 回包守卫 | `_send_response` 加 `_closed` 检查：关闭后 handler 副作用照常完成，回包跳过——避免对 deleted `interact_obj` emit 的 RuntimeError 噪音 |
| 线程属性 | `daemon=True` + `name=f'bridge-{tag}'`；句柄保留 `self._worker` 供排查 |
| `_event_lock` | 单 worker 下 dedup 访问实为单线程，锁冗余但保留不动（最小 diff） |
| 设计约束（三不变量） | 线程资源有界、生命周期可控、顺序确定——未来任何扩展不得突破 |
| 实施方式 | 当前分支单 commit，不自动提交 |

**未来演进（留口不预埋）**：若日后出现慢速非 DB handler（网络 I/O、大文件），按 handler 注册声明「车道」属性路由——默认 fast lane 走本方案 FIFO；慢速且不需顺序的只读 handler 进 slow lane（`ThreadPoolExecutor(max_workers=2~4)` 或第二条 worker+独立队列）。写操作永不进并行通道（防「保存后立刻删除」竞态）。入口收敛为队列后该扩展约 ~20 行增量，非重构。**永不回到裸线程**。

## 3. 改动清单

### 3.1 `lib/bridge_lib.py` — `BridgeDispatcher` 改队列驱动

```python
  def __init__(self, *, ...):
    # ...既有初始化不变...
    self._queue: queue.Queue[Optional[str]] = queue.Queue(maxsize=512)
    self._closed: bool = False
    self._worker = threading.Thread(
      target=self._worker_loop, daemon=True, name=f'bridge-{tag}')
    self._worker.start()

  def dispatch(self, message: str) -> None:
    """js2qt_signal 槽函数：GUI 线程触发，仅入队由常驻 worker 顺序分发"""
    if self._closed:
      APP_LOGGER.warning(f'[{self._tag}] dispatcher 已关闭，丢弃消息')
      return
    try:
      self._queue.put_nowait(message)
    except queue.Full:
      APP_LOGGER.warning(f'[{self._tag}] 消息队列已满（512），丢弃消息')

  def _worker_loop(self) -> None:
    while True:
      message = self._queue.get()
      if message is None:  # poison pill 排尾 → 自然排空存量消息后退出
        return
      self._dispatch_safe(message)

  def shutdown(self) -> None:
    """宿主关闭时调用：拒收新消息，已入队消息排空后 worker 退出（非阻塞）"""
    if self._closed:
      return
    self._closed = True
    self._queue.put(None)
```

`_send_response` 头部加守卫：

```python
    if self._closed:
      return
```

`_dispatch_safe`/`_dispatch`/`_handle_request`/`_handle_event` 零改动。

### 3.2 两弹窗 `closeEvent` 各 +1 行

```python
  def closeEvent(self, event: QEvent) -> None:
    if self._bridge is not None:
      self._bridge.shutdown()
    # ...既有 loading/devtools 清理不变...
    event.accept()
```

`_on_cleanup_done`（`app.py`）对两弹窗 `close()+deleteLater()` 路径自动经 closeEvent 触发 shutdown，无需改动。

### 3.3 `docs/reference/QT_BRIDGE.md`

L3 会话层「线程模型」段更新：无界 thread-per-message → 单 worker FIFO 队列语义（有界队列、FIFO 顺序、shutdown 排空、回包守卫、三不变量与 slow lane 演进约定）。

## 4. 影响面

| 项 | 说明 |
|---|---|
| 线程数 | 每消息 1 个无界 → 每 dispatcher 常驻 1 个（两弹窗最多 2 个），daemon=True |
| dispatch 耗时 | 入队 ~μs，比现状少一次线程 spawn（~0.5-1ms） |
| 响应时间 | 队列第 k 条等待增量 ≈ (k-1)×平均 handler 耗时 ≈ 毫秒级（实测单次 ≤0.2ms，放大 100 倍数据也就几 ms），低于感知阈值 |
| 处理顺序 | racy 并发 → 确定性 FIFO（行为改善） |
| 弹窗关闭 | 在途/已排队写操作排空完成，回包跳过（原 RuntimeError 噪音消除） |
| 退出路径 | 非 daemon 线程卡 `_shutdown` 的面消除（8s 看门狗仍兜底） |
| 调用方兼容 | `dispatch` 签名、`connect` 方式、handler 协议零改动 |
| 队头阻塞 | 理论风险与现状等价（慢 handler 占 DB 锁时并行模型同样被堵）；当前无慢 handler |

## 5. 行为等价与验收

bridge_lib 纯 Python 无 Qt 依赖，临时脚本即可验证核心语义（不入库）：

| 场景 | 构造 | 预期 |
|---|---|---|
| FIFO 顺序 | fake send + dispatch N 条 | 按入队序处理，单 worker |
| shutdown 排空 | 排队后 shutdown | 存量全部处理完，worker 退出 |
| 关闭后丢弃 | shutdown 后 dispatch | warn + 不入队 |
| 队列满丢弃 | 塞满 512 后继续发 | warn + drop，无阻塞无泄漏 |
| 关闭后回包跳过 | shutdown 时 handler 在途 | handler 完成、`send` 未调用 |

GUI 冒烟：两弹窗增删改查正常；快速连续操作无错乱；打开即关无异常日志。

```bash
uv run ruff check .   # 保持归零
```

## 6. 明确不做

- slow lane 并行通道实现（留演进约定，见 §2；当前无慢 handler，YAGNI）；
- 前端协议/载荷格式任何变更；
- event 去重逻辑（`_seen_event_ids`/`_event_lock`）改动；
- `create_thread` 其他使用处（报告 §9 独立问题）；
- 两弹窗 handler 业务逻辑任何改动。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| - | - | - | - |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| - | - | - |
