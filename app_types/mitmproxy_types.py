# -*- coding: utf-8 -*-
"""
mitmproxy 抓包相关的类型定义
"""
from typing import Dict, List, TypedDict, Union
from app_types.db_types import ApiRecord


class StaticRecord(TypedDict, total=False):
  """
  静态资源写入参数

  用于 save_static_to_cache 的入参，total=False 表示所有字段可选。
  """
  type: str  # 数据来源类型，如 'MITMPROXY'
  url: str  # 静态资源 URL


class MitmproxyConfig(TypedDict, total=False):
  """
  mitmproxy 抓包配置文件结构

  对应 config/mitmproxy_config.json 文件内容。
  """
  include_path: Union[str, List[str]]  # 抓包链接要包含的文本内容（正则字符串或正则字符串列表）
  static_include_path: List[str]  # 抓包静态资源链接要包含的文本内容（正则字符串列表）


class MitmproxyRunConfig(TypedDict, total=False):
  """
  mitmproxy 运行配置文件结构
  """
  host: str
  port: int
  work_dir: str
  mitmproxy_log: bool


# 抓包缓存数据结构: {search_key: {md5_key: ApiRecord, ...}, ...}
ResponseCacheDict = Dict[str, Dict[str, ApiRecord]]

# 静态资源缓存数据结构: {md5_key: StaticRecord, ...}
StaticCacheDict = Dict[str, StaticRecord]
