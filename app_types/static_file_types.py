# -*- coding: utf-8 -*-
"""
静态文件处理相关的类型定义
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, NamedTuple, Optional, TypedDict

from werkzeug.datastructures import Headers

from app_types.mock_server_types import FlaskRouteResult


# StaticFileHandler._resolve_file 返回类型
class ResolveFileResult(TypedDict):
  """路径解析 + 安全校验结果"""
  file_path: str
  file_name: str
  valid: bool
  result: Optional[FlaskRouteResult]  # valid=False 时为 (msg, status_code)


# StaticFileHandler 流式响应 meta
class ResponseMeta(NamedTuple):
  """流式响应 meta：status / headers / 字节区间 / content_length"""
  status: int
  headers: Dict[str, str]
  start: int
  end: int
  content_length: int


# Flask request.headers 实际类型
RequestHeaders = Headers

# 静态资源 URL 替换函数类型
AssetsReplaceFunc = Callable[[str], str]


class ThrottleStrategy(ABC):
  """限速策略统一接口"""

  @abstractmethod
  def create_reader(
      self,
      file_path: str,
      start: int,
      length: int,
  ) -> Any:
    """
    返回一个 file-like object（有 read() 方法）或 iterable[bytes]。
    WSGI server 通过 wsgi.file_wrapper 识别其 read() 方法，
    配合 Content-Length 头实现非 chunked 流式传输。
    """
    ...
