# -*- coding: utf-8 -*-
"""
GUI 相关的类型定义
"""
from typing import TypedDict


class AppServerRunningData(TypedDict):
  """
  APP_SERVER 启动结果数据

  用于 start_app_server 的返回值，以及 MainWindow / Dialog 中
  app_sever_running_data 的传递类型。
  """
  success: bool  # APP_SERVER 是否成功启动
  port: int  # APP_SERVER 监听端口号
