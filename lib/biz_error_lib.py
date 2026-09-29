# -*- coding: utf-8 -*-
"""
业务异常 → (status_code, status_msg) 解析工具

供 qt_win 下各 webview 弹窗的 _request 分发逻辑复用：
handler 抛出的异常按映射表转换为 Qt 响应协议中的业务状态码与状态消息。
"""
from typing import Optional, Sequence

from app_types.qt_bridge_types import BizStatus, ExcStatusRule
from config.enum.BIZ_CODE import (
  BIZ_UNKNOWN_ERROR,
  BIZ_PARAM_MISSING,
  BIZ_PARAM_INVALID,
  BIZ_FILE_READ_ERROR,
  BIZ_FILE_WRITE_ERROR,
)


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

  :param e: 捕获的异常
  :param exc_map: 自定义映射表，不传时使用 DEFAULT_EXC_STATUS_MAP；
    需要扩展私有规则时拼接在前面即可，如: _MY_MAP + DEFAULT_EXC_STATUS_MAP
  :return: (status_code, status_msg)，未匹配任何规则时兜底 BIZ_UNKNOWN_ERROR
  """
  for exc_type, code, fmt in (exc_map or DEFAULT_EXC_STATUS_MAP):
    if isinstance(e, exc_type):
      return code, fmt(e)
  return BIZ_UNKNOWN_ERROR, str(e)
