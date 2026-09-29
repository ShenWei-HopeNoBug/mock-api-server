# -*- coding: utf-8 -*-
"""
下载相关的类型定义
"""
from typing import List, TypedDict


class DownloadProxyItem(TypedDict, total=False):
  """
  单条下载代理配置（对应 download_config.json 中 download_proxy_list 的元素）

  消费端 get_download_proxies 通过 conf.get(key, 默认值) 读取，
  因此所有字段均为可选，缺省时走默认值。
  """
  protocol: str        # 代理协议，如 'http' / 'https'，对应 requests 的 proxies key
  proxy: str           # 代理地址，如 'http://127.0.0.1:7890'
  includes: List[str]  # URL 匹配规则列表，命中才走该代理


class GetDownloadProxyListResult(TypedDict):
  """
  /download_proxy/list 返回数据
  """
  list: List[DownloadProxyItem]  # 当前生效的代理配置列表


class UpdateDownloadProxyParams(TypedDict):
  """
  /download_proxy/update 请求参数

  全量覆盖式更新：传入的新列表会整体替换配置文件中的 download_proxy_list。
  """
  download_proxy_list: List[DownloadProxyItem]  # 新的代理配置列表
