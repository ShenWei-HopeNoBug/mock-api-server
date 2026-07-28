# -*- coding: utf-8 -*-
"""
GUI 相关的类型定义
"""
from typing import TypedDict


class GetMockDataParams(TypedDict, total=False):
  """
  get_mock_data 请求参数

  type 为数据来源类型过滤: 'USER' / 'MITMPROXY'，空值或不传表示全部。
  """
  type: str


class DeleteMockDataParams(TypedDict):
  """
  delete_mock_data 请求参数
  """
  id: str  # 待删除记录的 id


class AddMockDataParams(TypedDict, total=False):
  """
  add_mock_data / copy_mock_data 请求参数

  type 由 handler 硬编码为 'USER'，id 由 MockDB.insert_api 内部生成，均不需要前端传入。
  """
  url: str  # 请求 URL
  method: str  # HTTP 方法
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串


class AppServerRunningData(TypedDict):
  """
  APP_SERVER 启动结果数据

  用于 start_app_server 的返回值，以及 MainWindow / Dialog 中
  app_sever_running_data 的传递类型。
  """
  success: bool  # APP_SERVER 是否成功启动
  port: int  # APP_SERVER 监听端口号
