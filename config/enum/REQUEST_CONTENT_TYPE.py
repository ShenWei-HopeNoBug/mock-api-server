# -*- coding: utf-8 -*-
"""
HTTP 请求 content-type 枚举值
"""
from enum import Enum


class RequestContentType(str, Enum):
  """
  请求 content-type 枚举值

  用于统一描述请求体的内容类型，特别是 POST 请求。
  """
  NONE = 'NONE'
  APPLICATION_X_WWW_FORM_URLENCODED = 'APPLICATION_X_WWW_FORM_URLENCODED'
  APPLICATION_JSON = 'APPLICATION_JSON'
  MULTIPART_FORM_DATA = 'MULTIPART_FORM_DATA'


def get_request_content_type(content_type_header: str, method: str) -> RequestContentType:
  """
  根据 content-type header 和 HTTP 方法返回对应枚举值

  非 POST 方法或 POST 未匹配到以下三种类型时返回 NONE。
  """
  if method != 'POST':
    return RequestContentType.NONE

  raw = (content_type_header or '').lower()
  if 'application/x-www-form-urlencoded' in raw:
    return RequestContentType.APPLICATION_X_WWW_FORM_URLENCODED
  if 'application/json' in raw:
    return RequestContentType.APPLICATION_JSON
  if 'multipart/form-data' in raw:
    return RequestContentType.MULTIPART_FORM_DATA

  return RequestContentType.NONE
