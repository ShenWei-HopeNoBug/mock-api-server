# -*- coding: utf-8 -*-
"""
全局通用类型定义
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
