# -*- coding: utf-8 -*-
"""
请求相关的类型定义
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
