# -*- coding: utf-8 -*-
import json
import functools
import copy
from typing import Any, Callable, List

from lib.utils_lib import JsonFormat
from lib.logger_lib import APP_LOGGER


def _normalize_response_variant_ids(value: Any) -> str:
  """把 List[str] 或 JSON 字符串统一格式化为标准 JSON 字符串，缺省时返回 '[]'"""
  if value is None:
    variant_ids: List[str] = []
  elif isinstance(value, str):
    try:
      parsed = json.loads(value)
      variant_ids = [str(v) for v in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
      variant_ids = []
  elif isinstance(value, list):
    variant_ids = [str(v) for v in value]
  else:
    variant_ids = []
  return JsonFormat.dumps(variant_ids)


def _parse_response_variant_ids(value: Any) -> List[str]:
  """从数据库 JSON 字符串解析为 List[str]，失败时返回空列表"""
  if not value:
    return []
  try:
    parsed = json.loads(value)
    return [str(v) for v in parsed] if isinstance(parsed, list) else []
  except (json.JSONDecodeError, TypeError):
    return []


def _normalize_enabled(value: Any) -> int:
  """把 bool/int/None 统一转为 0/1，None 时默认启用"""
  if value is None:
    return 1
  return 1 if value else 0


def _parse_enabled(value: Any) -> bool:
  """把数据库 0/1 转为 bool"""
  return bool(value)


def _ensure_open(default: Any = None):
  """DB 方法保护装饰器，DB 已关闭时返回 default 而非抛异常"""

  def decorator(method: Callable) -> Callable:
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
      if self._closed:
        APP_LOGGER.warning(f'{self.__class__.__name__} 已关闭，{method.__name__} 未执行')
        return copy.deepcopy(default)
      return method(self, *args, **kwargs)

    return wrapper

  return decorator
