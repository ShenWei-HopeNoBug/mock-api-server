# -*- coding: utf-8 -*-
"""
mock server 相关的类型定义
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Protocol, Tuple, TypedDict, Union

from flask import Response
from werkzeug.datastructures import Headers

from app_types.global_types import JsonValue


class MockApiEntry(TypedDict):
  response: JsonValue
  timeout: int


class VariantMeta(TypedDict):
  """启用的 response 变体元数据（按 response_variant_ids 顺序排列）"""
  id: str
  timeout: int


class ApiMatchMeta(TypedDict):
  """轻量匹配元数据：只记录 id 和变体顺序，不存 response 大文本"""
  api_data_id: str
  timeout: int
  variants: List[VariantMeta]


# 业务语义类型别名
Route = str
HttpMethod = str
RequestContentTypeStr = str
ParamsJson = str
RequestKey = str
ResponseKey = str

# 原始参数输入类型（dict 或 JSON 字符串）
ParamsInput = Union[Dict[str, Any], str]

# mock api 轻量匹配映射: {request_key: {response_key: ApiMatchMeta, ...}, ...}
MockApiMap = Dict[RequestKey, Dict[ResponseKey, ApiMatchMeta]]

# 已废弃：旧的全量 response 映射表，保留别名避免外部引用报错
MockApiDict = Dict[RequestKey, Dict[ResponseKey, MockApiEntry]]

# Flask 路由函数的合法返回类型
FlaskRouteResult = Union[
  Response,
  Tuple[Response, int],
  Tuple[str, int],
]


# parse_flask_request 解析后的请求上下文
class ParsedRequest(NamedTuple):
  method: HttpMethod
  route: Route
  request_content_type: RequestContentTypeStr
  params: ParamsJson


# 将 dict 或 JSON 字符串统一序列化为标准 JSON 字符串的函数
class ParamsJsonStringFunc(Protocol):
  def __call__(self, params: ParamsInput) -> ParamsJson:
    ...


# 根据路由、HTTP 方法、content-type 生成 request_key 的函数
class RequestKeyFunc(Protocol):
  def __call__(
      self,
      route: Route,
      method: HttpMethod,
      request_content_type: RequestContentTypeStr,
  ) -> RequestKey:
    ...


# 根据 HTTP 方法、content-type、参数 JSON 生成 response_key 的函数
class ResponseKeyFunc(Protocol):
  def __call__(
      self,
      method: HttpMethod,
      request_content_type: RequestContentTypeStr,
      params: ParamsJson,
  ) -> ResponseKey:
    ...


# 设备标识
DeviceId = str

# 客户端状态
DeviceState = Dict[str, Any]


# 单个 api_data 在单设备上的变体命中状态
class VariantState(TypedDict):
  """记录某个设备对某个 api_data 的变体命中进度"""
  next_index: int  # 下次应命中的变体索引
  last_hit_time: float  # 上次命中时间戳（秒）
  last_variant_timeout: int  # 上次命中变体的 idle 回退超时（毫秒）


# ClientStateManager.get_or_create 返回结构
class ClientStateResult(TypedDict):
  device_id: DeviceId
  state: DeviceState
  is_new: bool


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
