# -*- coding: utf-8 -*-
"""
数据库相关的类型定义
"""
from typing import TypedDict


class ApiRecord(TypedDict, total=False):
  """
  API 数据写入参数

  用于 upsert_api / update_api / batch_upsert_api 的入参。
  total=False 表示所有字段可选，调用方按需传入。
  """
  id: str  # 记录唯一标识（upsert 时由代码生成，batch 时由外部传入）
  type: str  # 数据来源类型，如 'MITMPROXY' / 'USER'
  url: str  # 请求 URL
  method: str  # HTTP 方法，如 'GET' / 'POST'
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串


class ApiData(TypedDict):
  """
  API 数据完整记录

  用于 get_api_list 的返回值，包含数据库中的全部字段。
  """
  id: str  # 记录唯一标识
  type: str  # 数据来源类型
  url: str  # 请求 URL
  method: str  # HTTP 方法
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串
  created_at: str  # 创建时间，格式 'YYYY-MM-DD HH:MM:SS.sss'
  updated_at: str  # 更新时间，格式 'YYYY-MM-DD HH:MM:SS.sss'


class StaticData(TypedDict):
  """
  静态资源数据记录

  用于 get_static_list 的返回值。
  """
  url: str  # 静态资源 URL（主键）
  type: str  # 数据来源类型
  created_at: str  # 创建时间
  updated_at: str  # 更新时间
