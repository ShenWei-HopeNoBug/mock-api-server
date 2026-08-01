# -*- coding: utf-8 -*-
"""
mock server 相关的类型定义
"""
from typing import Dict, NamedTuple, Tuple, TypedDict, Union

from flask import Response

from app_types.global_types import JsonValue


class MockApiEntry(TypedDict):
  response: JsonValue
  timeout: int


# mock api 映射表结构: {request_key: {response_key: MockApiEntry, ...}, ...}
MockApiDict = Dict[str, Dict[str, MockApiEntry]]


# Flask 路由函数的合法返回类型
FlaskRouteResult = Union[
  Response,
  Tuple[Response, int],
  Tuple[str, int],
]


# parse_flask_request 解析后的请求上下文
class ParsedRequest(NamedTuple):
  method: str
  route: str
  request_content_type: str
  params: str
