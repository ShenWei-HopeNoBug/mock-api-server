# -*- coding: utf-8 -*-
"""
Qt Bridge 通信协议相关类型定义
"""
from typing import TypedDict

from app_types.global_types import JsonValue


# Qt → JS 响应消息结构（对应 QT_BRIDGE.md 响应方向协议）
class QtResponsePayload(TypedDict):
  type: str           # 固定 "response"
  name: str           # 请求名称
  action_id: str      # 与请求的 action_id 一一对应
  status_code: int    # 0=成功，非 0=失败
  status_msg: str     # 状态消息，失败时填充
  data: JsonValue     # 响应业务数据
