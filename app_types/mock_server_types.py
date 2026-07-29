# -*- coding: utf-8 -*-
"""
mock server 相关的类型定义
"""
from typing import Dict, TypedDict

from app_types.global_types import JsonValue


class MockApiEntry(TypedDict):
  response: JsonValue
  timeout: int


# mock api 映射表结构: {request_key: {response_key: MockApiEntry, ...}, ...}
MockApiDict = Dict[str, Dict[str, MockApiEntry]]
