# -*- coding: utf-8 -*-
import asyncio
from typing import Annotated, List, Optional
from multiprocessing import Process
from multiprocessing.synchronize import Event as EventType

import uvicorn
from mcp.server import MCPServer
from starlette.routing import Route
from starlette.responses import JSONResponse
from lib.logger_lib import APP_LOGGER
from lib.db import MockDBCache
from app_types.db_types import ApiData, ApiDataDetail, ApiQuery, ApiRecord, OperationResult, \
  OperationResultWithOptionalId
from app_types.mcp_server_types import McpServerRunConfig

# MCP 服务实例
mcp = MCPServer('mock-api-server')


# -------------------
# MCP 服务封装
# -------------------

class McpServer:
  def __init__(self, port: int = 8765, work_dir: str = '.', stop_event: Optional[EventType] = None) -> None:
    self.port: int = port
    self.work_dir: str = work_dir
    self.stop_event: Optional[EventType] = stop_event
    self._uvicorn_server: Optional[uvicorn.Server] = None
    # 注册 MCP 工具（闭包捕获 self.work_dir 访问 DB）
    self._register_tools()

  def _register_tools(self) -> None:
    """注册 MCP 工具，工具函数通过闭包捕获 self.work_dir 访问 DB"""

    def get_api_detail(
        api_id: Annotated[str, "API 记录的唯一标识 ID"],
    ) -> Optional[ApiDataDetail]:
      """
      查询指定 Mock API 的详细信息（含响应变体列表）。

      用途：根据 api_id 获取单条 API 的完整配置，包括 URL、HTTP 方法、
           请求参数、响应体、超时设置、启用状态，以及该 API 关联的
           所有 response 变体（同一接口的多种模拟响应）。

      场景：当需要查看某个 mock 接口的详细配置以判断是否需要修改，
           或需要了解某接口有哪些响应变体时调用。

      Args:
        api_id: API 记录的唯一标识 ID

      Returns:
        API 详情字典，包含以下字段：
        - id (str): 记录唯一标识
        - type (str): 数据来源类型，'MITMPROXY'(抓包导入) / 'USER'(手动创建) / 'MCP'(MCP工具创建)
        - url (str): 请求 URL
        - method (str): HTTP 方法，如 'GET'/'POST'/'PUT'/'DELETE'
        - params (str): 请求参数，JSON 字符串
        - response (str): 默认响应体，JSON 字符串
        - response_variant_ids (list[str]): 绑定的变体 ID 列表
        - response_variants (list[dict]): 变体详情列表，每项含 id/name/response/enabled/timeout/created_at/updated_at
        - enabled (bool): 是否启用
        - timeout (int): 超时时间（毫秒），0 表示不限制
        - request_content_type (str): 请求 content-type 枚举值
        - created_at (str): 创建时间
        - updated_at (str): 更新时间

        若 api_id 不存在则返回 None。
      """
      if not api_id:
        return None
      db = MockDBCache.get(self.work_dir)
      return db.get_api_detail(api_id)

    mcp.add_tool(get_api_detail)

    def list_mock_apis(
        url_like: Annotated[Optional[str], "按 URL 模糊搜索，为空则不筛选"] = None,
        method: Annotated[Optional[str], "HTTP 方法精确匹配，如 'GET'/'POST'/'PUT'/'DELETE'"] = None,
        api_type: Annotated[
          Optional[str], "数据来源类型精确匹配，'USER'(手动创建) / 'MITMPROXY'(抓包导入) / 'MCP'(MCP工具创建)"] = None,
        enabled: Annotated[Optional[bool], "按启用状态筛选，True 仅启用、False 仅禁用、None 不筛选"] = None,
        response_like: Annotated[Optional[str], "按响应体内容模糊搜索"] = None,
        params_like: Annotated[Optional[str], "按请求参数内容模糊搜索"] = None,
    ) -> List[ApiData]:
      """
      列出所有已配置的 Mock API 路由。

      用途：查询当前服务中有哪些 mock 接口，支持按 URL、HTTP 方法、
           启用状态等条件筛选。获取结果中的 id 字段后，可调用
           get_api_detail 查看详情，或调用 update_mock_api / delete_mock_api
           进行修改或删除。

      场景：当需要浏览现有 mock 接口列表、按条件搜索特定接口、
           或获取 api_id 用于后续操作时调用。

      Returns:
        列表，每项包含以下字段：
        - id (str): 记录唯一标识，可用于 get_api_detail / update_mock_api / delete_mock_api
        - type (str): 数据来源类型，'MITMPROXY'(抓包导入) / 'USER'(手动创建) / 'MCP'(MCP工具创建)
        - url (str): 请求 URL
        - method (str): HTTP 方法
        - params (str): 请求参数，JSON 字符串
        - response (str): 响应体，JSON 字符串
        - response_variant_ids (list[str]): 绑定的变体 ID 列表
        - enabled (bool): 是否启用
        - timeout (int): 超时时间（毫秒），0 表示不限制
        - request_content_type (str): 请求 content-type 枚举值
        - created_at (str): 创建时间
        - updated_at (str): 更新时间
      """
      query: ApiQuery = {}
      if url_like is not None:
        query['url_like'] = url_like
      if method is not None:
        query['method'] = method
      if api_type is not None:
        query['api_type'] = api_type
      if enabled is not None:
        query['enabled'] = enabled
      if response_like is not None:
        query['response_like'] = response_like
      if params_like is not None:
        query['params_like'] = params_like
      db = MockDBCache.get(self.work_dir)
      return db.get_api_list(query=query, reverse=True)

    mcp.add_tool(list_mock_apis)

    def update_mock_api(
        api_id: Annotated[str, "要修改的 API 记录 ID（必填），可通过 list_mock_apis 获取"],
        url: Annotated[Optional[str], "新的请求 URL"] = None,
        method: Annotated[Optional[str], "新的 HTTP 方法，如 'GET'/'POST'/'PUT'/'DELETE'"] = None,
        response: Annotated[Optional[str], "新的响应体，JSON 字符串"] = None,
        params: Annotated[Optional[str], "新的请求参数，JSON 字符串"] = None,
        enabled: Annotated[Optional[bool], "是否启用，True 启用 False 禁用"] = None,
        timeout: Annotated[Optional[int], "超时时间（毫秒），0 表示不限制"] = None,
    ) -> OperationResult:
      """
      修改指定 Mock API 的配置（字段级合并，仅更新传入的字段）。

      用途：修改某个 mock 接口的 URL、HTTP 方法、响应体、请求参数、
           启用状态或超时时间。未传入的字段保持原值不变。

      前置条件：需要先调用 list_mock_apis 获取 api_id。
      组合：修改后可调用 get_api_detail(api_id) 验证修改结果。

      Args:
        api_id: 要修改的 API 记录 ID（必填）
        url: 新的请求 URL（可选）
        method: 新的 HTTP 方法（可选）
        response: 新的响应体，JSON 字符串（可选）
        params: 新的请求参数，JSON 字符串（可选）
        enabled: 是否启用（可选）
        timeout: 超时时间，毫秒，0 表示不限制（可选）

      Returns:
        {"success": bool} 表示修改成功或失败。
      """
      record: ApiRecord = {'id': api_id}
      if url is not None:
        record['url'] = url
      if method is not None:
        record['method'] = method
      if response is not None:
        record['response'] = response
      if params is not None:
        record['params'] = params
      if enabled is not None:
        record['enabled'] = enabled
      if timeout is not None:
        record['timeout'] = timeout
      db = MockDBCache.get(self.work_dir)
      return db.update_api(record)

    mcp.add_tool(update_mock_api)

    def delete_mock_api(
        api_id: Annotated[str, "要删除的 API 记录 ID（必填），可通过 list_mock_apis 获取"],
    ) -> OperationResult:
      """
      删除指定的 Mock API 及其所有响应变体。

      用途：删除一个 mock 接口，同时级联删除该接口关联的所有
           response 变体。删除后该接口将不再提供 mock 服务。

      前置条件：需要先调用 list_mock_apis 获取 api_id。
      注意：删除操作不可恢复，请确认后再调用。

      Args:
        api_id: 要删除的 API 记录 ID（必填）

      Returns:
        {"success": bool} 表示删除成功或失败。
      """
      db = MockDBCache.get(self.work_dir)
      return db.delete_api(api_id)

    mcp.add_tool(delete_mock_api)

    def create_mock_api(
        url: Annotated[str, "请求 URL，如 'https://api.example.com/users'"],
        method: Annotated[str, "HTTP 方法，如 'GET'/'POST'/'PUT'/'DELETE'"],
        response: Annotated[str, "响应体，JSON 字符串，如 '{\"code\":0,\"data\":[]}'"] = '{}',
        params: Annotated[str, "请求参数，JSON 字符串，如 '{\"page\":\"1\"}'，GET 请求可传 '{}'"] = '{}',
        enabled: Annotated[bool, "是否启用，True 启用 False 禁用"] = True,
        timeout: Annotated[int, "超时时间（毫秒），0 表示不限制"] = 0,
    ) -> OperationResultWithOptionalId:
      """
      创建一个新的 Mock API 路由。

      用途：在 mock 服务中新增一个接口配置，指定 URL、HTTP 方法、
           响应体等。创建后该接口即可被 mock 服务匹配并返回模拟响应。
           数据来源类型固定标记为 'MCP'，便于区分由 MCP 工具创建的数据。

      组合：创建成功后返回 api_id，可调用 get_api_detail(api_id) 查看详情，
           或调用 update_mock_api(api_id, ...) 修改配置。

      Args:
        url: 请求 URL
        method: HTTP 方法
        response: 响应体，JSON 字符串（可选，默认 '{}'）
        params: 请求参数，JSON 字符串（可选，默认 '{}'）
        enabled: 是否启用（可选，默认 True）
        timeout: 超时时间，毫秒，0 表示不限制（可选，默认 0）

      Returns:
        dict（db.insert_api 返回值）:
        - success (bool): 是否创建成功
        - id (str | None): 新创建的记录 ID，可用于后续操作；失败时为 None
        - status_code (int): 状态码
        - status_msg (str): 结果描述
      """
      record: ApiRecord = {
        'type': 'MCP',
        'url': url,
        'method': method,
        'response': response,
        'params': params,
        'enabled': enabled,
        'timeout': timeout,
      }
      db = MockDBCache.get(self.work_dir)
      return db.insert_api(record)

    mcp.add_tool(create_mock_api)

  # 优雅关闭前的自定义清理逻辑
  async def _before_shutdown(self) -> None:
    """在触发 uvicorn 关闭前执行，关闭 DB 连接"""
    MockDBCache.close_all()

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
  work_dir = config.get('work_dir', '.')
  server = McpServer(port=port, work_dir=work_dir, stop_event=stop_event)
  server.start_server()


# 启动 MCP 服务
def start_mcp_server(config: McpServerRunConfig, stop_event: Optional[EventType] = None) -> Process:
  """启动 MCP 服务子进程"""
  print('Start MCP Server')
  mcp_process = Process(target=run_mcp_server, args=(config, stop_event), name='mcp_server')
  mcp_process.start()
  print('MCP Server is running')
  return mcp_process
