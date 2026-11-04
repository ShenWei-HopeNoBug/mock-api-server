# -*- coding: utf-8 -*-
"""
业务异常 → (status_code, status_msg) 解析工具

供 BridgeDispatcher（lib/bridge_lib.py）的 request 分发逻辑复用：
handler 抛出的异常按映射表转换为 Qt 响应协议中的业务状态码与状态消息。
"""
from typing import Optional, Sequence

from app_types.qt_bridge_types import BizStatus, ExcStatusRule
from config.enum.BIZ_CODE import (
  BIZ_FILE_READ_ERROR,
  BIZ_FILE_WRITE_ERROR,
  BIZ_PARAM_INVALID,
  BIZ_PARAM_MISSING,
  BIZ_UNKNOWN_ERROR,
)


class BizError(Exception):
  """
  业务异常：显式携带 status_code/status_msg

  用于表达 DEFAULT_EXC_STATUS_MAP 映射无法覆盖的业务错误（如数据不存在、
  约束冲突），resolve_biz_error 优先于默认映射表识别。
  """
  status_code: int
  status_msg: str

  def __init__(self, status_code: int, status_msg: str = '') -> None:
    super().__init__(status_msg)
    self.status_code = status_code
    self.status_msg = status_msg


# 默认异常映射表：(异常类型, status_code, 消息格式化函数)
# 按顺序 isinstance 匹配，具体异常类型需放在其父类之前
DEFAULT_EXC_STATUS_MAP = (
  (KeyError, BIZ_PARAM_MISSING, lambda e: f'缺少必填参数: {e}'),
  (ValueError, BIZ_PARAM_INVALID, str),
  (FileNotFoundError, BIZ_FILE_READ_ERROR, str),
  (PermissionError, BIZ_FILE_WRITE_ERROR, str),
)


def resolve_biz_error(
    e: Exception,
    exc_map: Optional[Sequence[ExcStatusRule]] = None,
) -> BizStatus:
  """
  将异常映射为 (status_code, status_msg)

  :param e: 捕获的异常；BizError 优先识别，直接取其 status_code/status_msg
    （status_msg 为空时回退 '操作失败'）
  :param exc_map: 自定义映射表，不传时使用 DEFAULT_EXC_STATUS_MAP；
    需要扩展私有规则时拼接在前面即可，如: _MY_MAP + DEFAULT_EXC_STATUS_MAP
  :return: (status_code, status_msg)，未匹配任何规则时兜底 BIZ_UNKNOWN_ERROR
  """
  if isinstance(e, BizError):
    return e.status_code, e.status_msg or '操作失败'
  for exc_type, code, fmt in (exc_map or DEFAULT_EXC_STATUS_MAP):
    if isinstance(e, exc_type):
      return code, fmt(e)
  return BIZ_UNKNOWN_ERROR, str(e)
