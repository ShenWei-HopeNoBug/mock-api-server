# -*- coding: utf-8 -*-
"""
mock server 相关的类型定义
"""
from typing import Dict, List, Union

# JSON 值类型（json.loads 返回值的精确类型）
JsonValue = Union[
  str,
  int,
  float,
  bool,
  None,
  Dict[str, 'JsonValue'],
  List['JsonValue'],
]

# mock api 映射表结构: {request_key: {response_key: JsonValue, ...}, ...}
MockApiDict = Dict[str, Dict[str, JsonValue]]
