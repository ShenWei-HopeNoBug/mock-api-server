# -*- coding: utf-8 -*-
"""
Qt Bridge 协议工具集

Phase 1（当前）：_unpack_result 载荷解包——将 DB 层 OperationResult 的
状态三元组（success/status_code/status_msg）从业务载荷中剥离，上提为
信封层状态，使信封 status_code 成为成败的唯一权威。

Phase 2（规划）：BridgeDispatcher 统一消息分发器，见
docs/v0_1_5/qt-bridge/qt-bridge-refactor-plan.md。

载荷键名契约：业务 data 不得使用 success / status_code / status_msg
三个键名，否则会被 _unpack_result 误识别为状态层。
"""
from typing import Any, Dict, NamedTuple

from config.enum.BIZ_CODE import BIZ_SUCCESS

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
