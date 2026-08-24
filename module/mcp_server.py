# -*- coding: utf-8 -*-
import asyncio
from typing import Optional
from multiprocessing import Process
from multiprocessing.synchronize import Event as EventType

import uvicorn
from mcp.server import MCPServer
from starlette.routing import Route
from starlette.responses import JSONResponse
from lib.logger_lib import APP_LOGGER
from app_types.mcp_server_types import McpServerRunConfig

# MCP 服务实例
mcp = MCPServer('mock-api-server')


# -------------------
# 测试工具（第一版，不接入 SQLite 数据库）
# -------------------

@mcp.tool()
def ping() -> str:
  """健康检查，返回 pong"""
  return 'pong'


@mcp.tool()
def echo(message: str) -> str:
  """原样返回输入消息，用于测试 MCP 通信链路"""
  return f'echo: {message}'


@mcp.tool()
def get_server_info() -> dict:
  """返回 MCP 服务基本信息，用于测试结构化返回值"""
  return {
    'name': 'mock-api-server',
    'version': 'v0.1.1',
    'status': 'running',
    'tools': ['ping', 'echo', 'get_server_info'],
  }


# -------------------
# MCP 服务封装
# -------------------

class McpServer:
  def __init__(self, port: int = 8765, stop_event: Optional[EventType] = None) -> None:
    self.port: int = port
    self.stop_event: Optional[EventType] = stop_event
    self._uvicorn_server: Optional[uvicorn.Server] = None

  # 优雅关闭前的自定义清理逻辑（占位函数，后续按需实现）
  async def _before_shutdown(self) -> None:
    """在触发 uvicorn 关闭前执行，用于保存数据等清理操作"""
    pass

  # 轮询 stop_event，检测到后先执行 _before_shutdown，再设置 should_exit 优雅关闭
  async def _stop_watcher(self) -> None:
    while not self.stop_event.is_set():
      await asyncio.sleep(0.5)
    APP_LOGGER.info('MCP_SERVER 收到 stop_event 信号，正在优雅关闭...')
    # 1. 先执行自定义保存/清理逻辑
    await self._before_shutdown()
    # 2. 再触发 uvicorn 优雅关闭
    if self._uvicorn_server is not None:
      self._uvicorn_server.should_exit = True

  # 启动 MCP 服务
  def start_server(self) -> None:
    print('>' * 10, 'MCP 服务启动...')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
      loop.run_until_complete(self._serve())
    finally:
      loop.close()

  async def _serve(self) -> None:
    # 获取 MCP 底层 Starlette app，添加 /ping 路由
    app = mcp.streamable_http_app()
    app.routes.append(Route('/ping', lambda request: JSONResponse({'data': 'pong!'}), methods=['GET']))

    config = uvicorn.Config(app, host='127.0.0.1', port=self.port, log_level='info')
    self._uvicorn_server = uvicorn.Server(config)

    # 启动 stop_event 监听协程
    if self.stop_event is not None:
      asyncio.ensure_future(self._stop_watcher())

    await self._uvicorn_server.serve()


# -------------------
# 进程管理（与 asyncio_mitmproxy_server.py 结构对齐）
# -------------------

# MCP 服务进程入口
def run_mcp_server(config: McpServerRunConfig, stop_event: Optional[EventType] = None) -> None:
  """运行 MCP 服务"""
  print('mcp_config', config)
  port = config.get('port', 8765)
  server = McpServer(port=port, stop_event=stop_event)
  server.start_server()


# 启动 MCP 服务
def start_mcp_server(config: McpServerRunConfig, stop_event: Optional[EventType] = None) -> Process:
  """启动 MCP 服务子进程"""
  print('Start MCP Server')
  mcp_process = Process(target=run_mcp_server, args=(config, stop_event), name='mcp_server')
  mcp_process.start()
  print('MCP Server is running')
  return mcp_process
