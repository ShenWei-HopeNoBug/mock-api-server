# -*- coding: utf-8 -*-
"""
MCP 服务相关的类型定义
"""
from typing import TypedDict


class McpServerRunConfig(TypedDict, total=False):
  """
  MCP 服务运行配置

  用于 start_mcp_server / run_mcp_server 的入参，
  与 MitmproxyRunConfig 结构对齐。
  """
  port: int  # MCP 服务监听端口号，默认 8765
  work_dir: str  # APP 工作目录绝对路径，用于定位 SQLite 数据库
