# -*- coding: utf-8 -*-
"""
mock server 相关的类型定义
"""
from typing import Dict

from app_types.global_types import JsonValue

# mock api 映射表结构: {request_key: {response_key: JsonValue, ...}, ...}
MockApiDict = Dict[str, Dict[str, JsonValue]]
