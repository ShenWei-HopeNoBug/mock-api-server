# -*- coding: utf-8 -*-
"""
mock server 相关的类型定义
"""
from typing import Any, Dict, NamedTuple, Protocol, Tuple, TypedDict, Union

from flask import Response

from app_types.global_types import JsonValue


class MockApiEntry(TypedDict):
  response: JsonValue
  timeout: int


# 业务语义类型别名
Route = str
HttpMethod = str
RequestContentTypeStr = str
ParamsJson = str
RequestKey = str
ResponseKey = str

# 原始参数输入类型（dict 或 JSON 字符串）
ParamsInput = Union[Dict[str, Any], str]

# mock api 映射表结构: {request_key: {response_key: MockApiEntry, ...}, ...}
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
