# -*- coding: utf-8 -*-
"""
Qt Bridge 通信协议相关类型定义
"""
from typing import Any, Callable, Dict, Literal, Tuple, Type, TypedDict, Union

from app_types.global_types import JsonValue


class QtBridgeRequest(TypedDict):
  type: Literal['request']
  name: str
  action_id: str
  params: Dict[str, Any]
  data: Any


class _QtBridgeEventOptionalFields(TypedDict, total=False):
  params: Dict[str, Any]
  data: Any


class QtBridgeEvent(_QtBridgeEventOptionalFields):
  type: Literal['event']
  name: str
  action_id: str


QtBridgeIncomingMessage = Union[QtBridgeRequest, QtBridgeEvent]


# Qt → JS 响应消息结构（对应 QT_BRIDGE.md 响应方向协议）
class QtResponsePayload(TypedDict):
  type: str           # 固定 "response"
  name: str           # 请求名称
  action_id: str      # 与请求的 action_id 一一对应
  status_code: int    # 业务状态码，0=成功，非 0=失败（详见 config/enum/BIZ_CODE.py）
  status_msg: str     # 状态消息，失败时填充
  data: JsonValue     # 响应业务数据


# 异常 → (status_code, status_msg) 映射规则：(异常类型, 业务状态码, 消息格式化函数)
# 配合 lib/biz_error_lib.resolve_biz_error 使用，按顺序 isinstance 匹配，具体异常类型放前面
ExcStatusRule = Tuple[Type[Exception], int, Callable[[Exception], str]]

# resolve_biz_error 的返回类型：(status_code, status_msg)
BizStatus = Tuple[int, str]
