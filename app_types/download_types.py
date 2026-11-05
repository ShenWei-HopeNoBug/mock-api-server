# -*- coding: utf-8 -*-
"""
下载相关的类型定义
"""
from typing import Any, Dict, List, Protocol, TypedDict

from requests import Response


class DownloadProxyItem(TypedDict, total=False):
  """
  单条下载代理配置（对应 download_config.json 中 download_proxy_list 的元素）

  消费端 StaticAssetDownloader._get_proxies 通过 conf.get(key, 默认值) 读取，
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


class DownloadConfig(TypedDict, total=False):
  """
  download_config.json 整体结构（对应 config/work_file.py 的 DOWNLOAD_CONFIG.default）

  配置文件允许部分缺失，所有字段均按 get(key, 默认值) 读取。
  """
  include_files: List[str]                      # 要匹配的静态资源链接扩展名列表
  download_timeout: int                         # 下载连接超时时间（s）
  auto_adjust_timeout: bool                     # 是否按域名连续连接失败次数动态收缩超时
  download_proxy_list: List[DownloadProxyItem]  # 下载代理配置列表


class DownloadLogBase(TypedDict):
  """
  下载日志条目的静态字段部分（url/save_path/file_name/proxies）
  """
  url: str                 # 静态资源原始 URL
  save_path: str           # 本地落盘绝对路径
  file_name: str           # 落盘文件名（URL 末段 basename）
  proxies: Dict[str, str]  # 本次下载实际使用的代理


class DownloadLogItem(DownloadLogBase):
  """
  download/<log_name>.json 中的单条下载日志（StaticAssetDownloader._append_log 产出）
  """
  success: bool  # 下载是否成功（导出静态资源按此字段过滤）
  message: str   # 失败原因/备注，成功为空串


class OutputStaticItem(TypedDict):
  """
  get_output_data_list 产出的单条导出项
  """
  path: str       # 静态资源本地绝对路径
  file_name: str  # 文件名


class DownloadProgressItem(TypedDict):
  """
  StaticAssetDownloader 下载进度回调的 payload
  """
  current: int  # 当前序号（1 起）
  total: int    # 待下载总数
  asset: str    # 当前下载的 URL


class HttpGetSession(Protocol):
  """
  StaticAssetDownloader 会话注入点的最小契约

  requests 模块本身与 requests.Session 实例均满足该结构；
  测试时可注入返回固定 Response 的 mock。
  """
  def get(self, url: str, **kwargs: Any) -> Response: ...
