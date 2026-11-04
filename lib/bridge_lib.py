# -*- coding: utf-8 -*-
"""
Qt Bridge 协议工具集（纯 Python，不依赖 Qt，便于单元测试）

- _unpack_result：载荷解包——将 DB 层 OperationResult 的状态三元组
  （success/status_code/status_msg）剥离上提为信封层状态，信封
  status_code 是成败的唯一权威。
- BridgeDispatcher：JS→Qt 消息统一分发器，收敛原各 webview 弹窗
  内复制的接收/校验/路由/回包/事件去重逻辑。

载荷键名契约：业务 data 不得使用 success / status_code / status_msg
三个键名，否则会被 _unpack_result 误识别为状态层。
"""
import json
import re
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Generic, Mapping, NamedTuple, Optional, Sequence, Tuple

from app_types.qt_bridge_types import (
  BridgeSendFn,
  CtxT,
  EventHandler,
  ExcStatusRule,
  QtResponsePayload,
  RequestHandler,
)
from config.enum.BIZ_CODE import BIZ_PARAM_INVALID, BIZ_SUCCESS
from lib.biz_error_lib import DEFAULT_EXC_STATUS_MAP, resolve_biz_error
from lib.logger_lib import APP_LOGGER

# 状态三元组键：OperationResult 的状态层字段，剥离时不进业务载荷
# （success 在 DB 层删除前仍会出现在旧载荷中，保留在集合内兼容）
_STATUS_KEYS = {'success', 'status_code', 'status_msg'}


class UnpackedResult(NamedTuple):
  """OperationResult 解包结果：信封状态层 + 剥离后的业务载荷"""
  status_code: int
  status_msg: str
  data: Any


def _unpack_result(result: Any) -> UnpackedResult:
  """
  识别 OperationResult 形态（dict 且 status_code 为 int）：
  状态三元组上提信封，业务字段剥离为 data。

  - 判定只看 status_code（成败唯一事实源），success 是否在场不影响
  - 成功：剥离三元组，剩余业务字段作 data（剥空 → None）
  - 失败：信封取 result 的 code/msg，data=None（与异常路径一致）
  - 非结果形态（list/detail/None 等）：原样直通
  """
  if isinstance(result, dict) and isinstance(result.get('status_code'), int):
    code: int = result['status_code']
    if code == BIZ_SUCCESS:
      data: Dict[str, Any] = {k: v for k, v in result.items() if k not in _STATUS_KEYS}
      return UnpackedResult(BIZ_SUCCESS, '', data or None)
    return UnpackedResult(code, result.get('status_msg') or '操作失败', None)
  return UnpackedResult(BIZ_SUCCESS, '', result)


class BridgeDispatcher(Generic[CtxT]):
  """
  Qt Bridge 消息统一分发器

  职责：
    - JSON 解析与 request/event 分流
    - request：action_id/name/params 校验 → 路由 → handler → _unpack_result → 回包
    - event：校验 → (name, action_id) 去重 → handler（无回包）
    - 统一日志：[{tag}] {name} action_id={action_id} code={status_code} cost={ms}ms

  接入方式（webview 弹窗）：

    self._bridge = BridgeDispatcher(
      send=interact_obj.send_qt2js_dict_msg,
      request_handlers=self._REQUEST_HANDLERS,
      event_handlers=self._EVENT_HANDLERS,   # 无 event 时可省略
      handler_context=self,
      tag='dataManager',
    )
    interact_obj.js2qt_signal.connect(self._bridge.dispatch)

  注意：dispatcher 必须由宿主强引用持有（如 self._bridge），否则 bound
  method 被 GC 后信号连接会静默断开，前端请求全部超时。
  """

  # 非法 JSON 兜底：从原始消息文本中正则提取 action_id 以便回包
  _ACTION_ID_RE = re.compile(r'"action_id"\s*:\s*"([^"]+)"')

  def __init__(
      self,
      *,
      send: BridgeSendFn,
      request_handlers: Mapping[str, RequestHandler[CtxT]],
      handler_context: CtxT,
      event_handlers: Optional[Mapping[str, EventHandler[CtxT]]] = None,
      extra_exc_map: Optional[Sequence[ExcStatusRule]] = None,
      dedup_size: int = 256,
      tag: str = 'bridge',
  ) -> None:
    self._send = send
    self._request_handlers = request_handlers
    self._event_handlers = event_handlers or {}
    self._ctx = handler_context
    # extra 规则拼在默认表之前，与 resolve_biz_error 的自定义映射用法一致
    self._exc_map = tuple(extra_exc_map) + DEFAULT_EXC_STATUS_MAP if extra_exc_map else None
    self._dedup_size = dedup_size
    self._tag = tag
    self._seen_event_ids: OrderedDict[Tuple[str, str], None] = OrderedDict()
    self._event_lock = threading.Lock()

  # ---- 入口 ----

  def dispatch(self, message: str) -> None:
    """js2qt_signal 槽函数：GUI 线程触发，内部开 worker 线程执行分发"""
    threading.Thread(target=self._dispatch_safe, args=(message,)).start()

  def _dispatch_safe(self, message: str) -> None:
    try:
      self._dispatch(message)
    except Exception as e:
      APP_LOGGER.error(f'[{self._tag}] bridge 消息分发异常: {e}', exc_info=True)

  def _dispatch(self, message: str) -> None:
    try:
      incoming = json.loads(message)
    except (ValueError, TypeError):
      self._reply_invalid_message(message)
      return
    if not isinstance(incoming, dict):
      self._reply_invalid_message(message)
      return

    msg_type = incoming.get('type')
    if msg_type == 'request':
      self._handle_request(incoming)
    elif msg_type == 'event':
      self._handle_event(incoming)
    else:
      APP_LOGGER.warning(f'[{self._tag}] 未知消息类型，丢弃: type={msg_type}')

  def _reply_invalid_message(self, message: str) -> None:
    """非法 JSON / 非对象消息：能提取 action_id 则回 PARAM_INVALID，否则记日志丢弃"""
    match = self._ACTION_ID_RE.search(message)
    if match:
      self._send_response('', match.group(1), None, BIZ_PARAM_INVALID, '请求格式非法')
    else:
      APP_LOGGER.warning(f'[{self._tag}] 非法消息且无 action_id，丢弃: {message[:200]}')

  # ---- request ----

  def _handle_request(self, incoming: Dict[str, Any]) -> None:
    name = incoming.get('name')
    action_id = incoming.get('action_id')
    # action_id 缺失无法回包，只能丢弃（不执行 handler）
    if not isinstance(action_id, str) or not action_id:
      APP_LOGGER.warning(f'[{self._tag}] request 缺少 action_id，丢弃: name={name}')
      return
    if not isinstance(name, str) or not name:
      self._send_response('', action_id, None, BIZ_PARAM_INVALID, '缺少请求路径')
      return
    params = incoming.get('params')
    # params 缺省视为 {}，非对象一律拒绝
    if params is None:
      params = {}
    if not isinstance(params, dict):
      self._send_response(name, action_id, None, BIZ_PARAM_INVALID, 'params 必须是对象')
      return

    handler = self._request_handlers.get(name)
    if handler is None:
      self._send_response(name, action_id, None, BIZ_PARAM_INVALID, f'不支持的请求路径: {name}')
      return

    start = time.perf_counter()
    try:
      result = handler(self._ctx, params)
      unpacked = _unpack_result(result)
    except Exception as e:
      # 具体错误进日志，不向前端泄露内部异常文本之外的信息
      APP_LOGGER.error(f'[{self._tag}] {name} handler 异常: {e}', exc_info=True)
      code, msg = resolve_biz_error(e, self._exc_map)
      unpacked = UnpackedResult(code, msg, None)
    cost_ms = (time.perf_counter() - start) * 1000

    self._send_response(name, action_id, unpacked.data, unpacked.status_code, unpacked.status_msg)
    APP_LOGGER.info(
      f'[{self._tag}] {name} action_id={action_id} code={unpacked.status_code} cost={cost_ms:.1f}ms'
    )

  # ---- event ----

  def _handle_event(self, incoming: Dict[str, Any]) -> None:
    name = incoming.get('name')
    action_id = incoming.get('action_id')
    if not isinstance(name, str) or not isinstance(action_id, str) or not action_id:
      APP_LOGGER.warning(f'[{self._tag}] event 缺少 name/action_id，丢弃')
      return
    handler = self._event_handlers.get(name)
    if handler is None:
      APP_LOGGER.warning(f'[{self._tag}] 未注册的 event: {name}')
      return

    # worker 线程并发执行，检查与写入需加锁；容量超限时淘汰最早记录
    key = (name, action_id)
    with self._event_lock:
      if key in self._seen_event_ids:
        return
      self._seen_event_ids[key] = None
      while len(self._seen_event_ids) > self._dedup_size:
        self._seen_event_ids.popitem(last=False)

    try:
      handler(self._ctx, incoming)
    except Exception as e:
      # 处理失败不计入已完成事件，允许相同 action_id 重试
      with self._event_lock:
        self._seen_event_ids.pop(key, None)
      APP_LOGGER.error(f'[{self._tag}] event {name} handler 异常: {e}', exc_info=True)

  # ---- 回包 ----

  def _send_response(
      self,
      name: str,
      action_id: str,
      data: Any,
      status_code: int,
      status_msg: str,
  ) -> None:
    payload: QtResponsePayload = {
      "type": "response",
      "name": name,
      "action_id": action_id or '',
      "status_code": status_code,
      "status_msg": status_msg,
      "data": data,
    }
    self._send(payload)
