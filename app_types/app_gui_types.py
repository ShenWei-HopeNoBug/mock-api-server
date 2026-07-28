# -*- coding: utf-8 -*-
"""
GUI 相关的类型定义
"""
from typing import Literal, TypedDict


class GetMockDataParams(TypedDict, total=False):
  """
  get_mock_data 请求参数

  type 为数据来源类型过滤: 'USER' / 'MITMPROXY'，空值或不传表示全部。
  """
  type: Literal['USER', 'MITMPROXY']


class GetMockDataPageParams(TypedDict, total=False):
  """
  get_mock_data_page 请求参数（分页版）

  type 为数据来源类型过滤: 'USER' / 'MITMPROXY'，空值或不传表示全部（USER 在前）。
  """
  type: Literal['USER', 'MITMPROXY']
  page_num: int   # 1-based 页码
  page_size: int  # 每页条数


class DeleteMockDataParams(TypedDict):
  """
  delete_mock_data 请求参数
  """
  id: str  # 待删除记录的 id


class AddMockDataParams(TypedDict, total=False):
  """
  add_mock_data 请求参数

  type 由 handler 硬编码为 'USER'，id 由 MockDB.insert_api 内部生成，均不需要前端传入。
  """
  url: str  # 请求 URL
  method: str  # HTTP 方法
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串


class CopyMockDataParams(TypedDict):
  """
  copy_mock_data 请求参数

  只需传源记录的 id，handler 按 id 查库取完整数据后复制插入。
  """
  id: str  # 待复制的源记录 id


class AppServerRunningData(TypedDict):
  """
  APP_SERVER 启动结果数据

  用于 start_app_server 的返回值，以及 MainWindow / Dialog 中
  app_sever_running_data 的传递类型。
  """
  success: bool  # APP_SERVER 是否成功启动
  port: int  # APP_SERVER 监听端口号
