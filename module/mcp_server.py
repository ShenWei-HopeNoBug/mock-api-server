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
from app_types.db_types import (
  ApiDataDetail,
  ApiQuery,
  ApiRecord,
  ApiResponseVariant,
  ApiResponseVariantInsertRecord,
  ApiResponseVariantRecord,
  ApiSummary,
  OperationResult,
  OperationResultWithOptionalId,
  PaginatedApiList,
)
from app_types.mcp_server_types import McpServerRunConfig


# -------------------
# MCP 服务封装
# -------------------

class McpServer:
  def __init__(self, port: int = 8765, work_dir: str = '.', stop_event: Optional[EventType] = None, mcp_log: bool = True) -> None:
    self.port: int = port
    self.work_dir: str = work_dir
    self.stop_event: Optional[EventType] = stop_event
    self.mcp_log: bool = mcp_log
    self._uvicorn_server: Optional[uvicorn.Server] = None
    # MCP 服务实例（每个 McpServer 独享，避免多实例工具注册冲突）
    self.mcp = MCPServer('mock-api-server')
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
        - method (str): HTTP 方法，'GET' 或 'POST'
        - params (str): 请求参数，JSON 字符串
        - response (str): 默认响应体，JSON 字符串
        - response_variant_ids (list[str]): 绑定的变体 ID 列表
        - response_variants (list[dict]): 变体详情列表，每项含 id/name/response/enabled/timeout/created_at/updated_at
        - enabled (bool): 是否启用
        - timeout (int): 超时时间（毫秒），0 表示不限制
        - request_content_type (str): 请求 content-type 枚举值: 'NONE' / 'APPLICATION_JSON' / 'MULTIPART_FORM_DATA' / 'APPLICATION_X_WWW_FORM_URLENCODED'
        - created_at (str): 创建时间
        - updated_at (str): 更新时间

        若 api_id 不存在则返回 None。
      """
      if not api_id:
        return None
      db = MockDBCache.get(self.work_dir)
      return db.get_api_detail(api_id)

    self.mcp.add_tool(get_api_detail)

    def list_mock_apis(
        url_like: Annotated[Optional[str], "按 URL 模糊搜索，为空则不筛选"] = None,
        method: Annotated[Optional[str], "HTTP 方法精确匹配，仅支持 'GET' 或 'POST'"] = None,
        api_type: Annotated[
          Optional[str], "数据来源类型精确匹配，'USER'(手动创建) / 'MITMPROXY'(抓包导入) / 'MCP'(MCP工具创建)"] = None,
        enabled: Annotated[Optional[bool], "按启用状态筛选，True 仅启用、False 仅禁用、None 不筛选"] = None,
        response_like: Annotated[Optional[str], "按响应体内容模糊搜索"] = None,
        params_like: Annotated[Optional[str], "按请求参数内容模糊搜索"] = None,
        request_content_type: Annotated[Optional[
          str], "请求 content-type 枚举值精确匹配，可选值: 'NONE' / 'APPLICATION_JSON' / 'MULTIPART_FORM_DATA' / 'APPLICATION_X_WWW_FORM_URLENCODED'"] = None,
        page_num: Annotated[int, "页码（从 1 开始），默认 1"] = 1,
        page_size: Annotated[int, "每页条数，默认 20，最大 100"] = 20,
    ) -> PaginatedApiList:
      """
      列出已配置的 Mock API 路由（分页 + 精简字段）。

      用途：查询当前服务中有哪些 mock 接口，支持按 URL、HTTP 方法、
           启用状态等条件筛选和分页。返回精简字段列表（不含 response、params
           等大字段），获取结果中的 id 字段后，可调用 get_api_detail 查看完整详情，
           或调用 update_mock_api / delete_mock_api 进行修改或删除。

      场景：当需要浏览现有 mock 接口列表、按条件搜索特定接口、
           或获取 api_id 用于后续操作时调用。
           数据量较大时通过 page_num 和 page_size 分页获取，has_more 为 True 表示还有更多数据。

      Args:
        url_like: 按 URL 模糊搜索
        method: HTTP 方法精确匹配
        api_type: 数据来源类型精确匹配
        enabled: 按启用状态筛选
        response_like: 按响应体内容模糊搜索
        params_like: 按请求参数内容模糊搜索
        request_content_type: 请求 content-type 枚举值精确匹配
        page_num: 页码（从 1 开始），默认 1
        page_size: 每页条数，默认 20，最大 100

      Returns:
        分页响应字典，包含以下字段：
        - total (int): 符合筛选条件的记录总数
        - page_num (int): 当前页码
        - page_size (int): 每页条数
        - has_more (bool): 是否还有更多数据
        - list (list): 当前页的精简记录列表，每项包含：
          - id (str): 记录唯一标识，可用于 get_api_detail / update_mock_api / delete_mock_api
          - type (str): 数据来源类型，'MITMPROXY'(抓包导入) / 'USER'(手动创建) / 'MCP'(MCP工具创建)
          - url (str): 请求 URL
          - method (str): HTTP 方法，'GET' 或 'POST'
          - enabled (bool): 是否启用
          - timeout (int): 超时时间（毫秒），0 表示不限制
          - request_content_type (str): 请求 content-type 枚举值
          - operator (str): 操作来源
          - created_at (str): 创建时间
          - updated_at (str): 更新时间

        注意：列表仅返回精简字段，不含 response、params、response_variant_ids。
        需要完整信息时请调用 get_api_detail(api_id)。
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
      if request_content_type is not None:
        query['request_content_type'] = request_content_type

      page_num = max(1, page_num)
      page_size = max(1, min(page_size, 100))

      db = MockDBCache.get(self.work_dir)
      total = db.get_api_count(query=query)
      rows = db.get_api_list_page(query=query, reverse=True, page_num=page_num, page_size=page_size)

      items: List[ApiSummary] = [{
        'id': row['id'],
        'type': row['type'],
        'url': row['url'],
        'method': row['method'],
        'enabled': row['enabled'],
        'timeout': row['timeout'],
        'request_content_type': row['request_content_type'],
        'operator': row['operator'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
      } for row in rows]

      return {
        'total': total,
        'page_num': page_num,
        'page_size': page_size,
        'has_more': page_num * page_size < total,
        'list': items,
      }

    self.mcp.add_tool(list_mock_apis)

    def update_mock_api(
        api_id: Annotated[str, "要修改的 API 记录 ID（必填），可通过 list_mock_apis 获取"],
        url: Annotated[Optional[str], "新的请求 URL"] = None,
        method: Annotated[Optional[str], "新的 HTTP 方法，仅支持 'GET' 或 'POST'"] = None,
        response: Annotated[Optional[str], "新的响应体，JSON 字符串"] = None,
        params: Annotated[Optional[str], "新的请求参数，JSON 字符串"] = None,
        enabled: Annotated[Optional[bool], "是否启用，True 启用 False 禁用"] = None,
        timeout: Annotated[Optional[int], "超时时间（毫秒），0 表示不限制"] = None,
        request_content_type: Annotated[Optional[
          str], "新的请求 content-type 枚举值，可选值: 'NONE' / 'APPLICATION_JSON' / 'MULTIPART_FORM_DATA' / 'APPLICATION_X_WWW_FORM_URLENCODED'；GET 请求固定为 'NONE'"] = None,
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
        request_content_type: 新的请求 content-type 枚举值（可选）；GET 请求固定为 'NONE'

      Returns:
        {"success": bool} 表示修改成功或失败。
      """
      record: ApiRecord = {'id': api_id, 'operator': 'MCP'}
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
      if request_content_type is not None:
        record['request_content_type'] = request_content_type
      db = MockDBCache.get(self.work_dir)
      return db.update_api(record)

    self.mcp.add_tool(update_mock_api)

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

    self.mcp.add_tool(delete_mock_api)

    def create_mock_api(
        url: Annotated[str, "请求 URL，如 'https://api.example.com/users'"],
        method: Annotated[str, "HTTP 方法，仅支持 'GET' 或 'POST'"],
        response: Annotated[str, "响应体，JSON 字符串，如 '{\"code\":0,\"data\":[]}'"] = '{}',
        params: Annotated[str, "请求参数，JSON 字符串，如 '{\"page\":\"1\"}'，GET 请求可传 '{}'"] = '{}',
        enabled: Annotated[bool, "是否启用，True 启用 False 禁用"] = True,
        timeout: Annotated[int, "超时时间（毫秒），0 表示不限制"] = 0,
        request_content_type: Annotated[
          str, "请求 content-type 枚举值，可选值: 'NONE' / 'APPLICATION_JSON' / 'MULTIPART_FORM_DATA' / 'APPLICATION_X_WWW_FORM_URLENCODED'；GET 请求固定为 'NONE'，默认 'NONE'"] = 'NONE',
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
        request_content_type: 请求 content-type 枚举值（可选，默认 'NONE'）；GET 请求固定为 'NONE'，POST 请求可传 'APPLICATION_JSON' / 'MULTIPART_FORM_DATA' / 'APPLICATION_X_WWW_FORM_URLENCODED'

      Returns:
        dict（db.insert_api 返回值）:
        - success (bool): 是否创建成功
        - id (str | None): 新创建的记录 ID，可用于后续操作；失败时为 None
        - status_code (int): 状态码
        - status_msg (str): 结果描述
      """
      record: ApiRecord = {
        'type': 'MCP',
        'operator': 'MCP',
        'url': url,
        'method': method,
        'response': response,
        'params': params,
        'enabled': enabled,
        'timeout': timeout,
        'request_content_type': request_content_type,
      }
      db = MockDBCache.get(self.work_dir)
      return db.insert_api(record)

    self.mcp.add_tool(create_mock_api)

    # ---- 响应变体管理工具 ----

    def list_response_variants(
        api_id: Annotated[str, "所属 API 记录的 ID（必填），可通过 list_mock_apis 获取"],
        enabled: Annotated[Optional[bool], "按启用状态筛选，True 仅启用、False 仅禁用、None 不筛选"] = None,
    ) -> List[ApiResponseVariant]:
      """
      列出指定 Mock API 的所有响应变体。

      用途：查询某个 mock 接口下配置了哪些不同的模拟响应（如成功响应、
           错误响应、超时响应等），支持按启用状态筛选。

      场景：当需要查看某接口有哪些变体、或需要获取 variant_id 用于
          后续修改/删除/复制时调用。

      Args:
        api_id: 所属 API 记录的 ID（必填）
        enabled: 按启用状态筛选（可选）

      Returns:
        列表，每项包含以下字段：
        - id (str): 变体唯一标识，可用于 update_response_variant / delete_response_variant / copy_response_variant
        - api_data_id (str): 所属 API 记录 ID
        - name (str): 变体名称
        - response (str): 变体响应体，JSON 字符串
        - enabled (bool): 是否启用
        - timeout (int): 超时时间（毫秒），0 表示不限制
        - created_at (str): 创建时间
        - updated_at (str): 更新时间
      """
      db = MockDBCache.get(self.work_dir)
      return db.get_variants_by_api_id(api_id, enabled=enabled)

    self.mcp.add_tool(list_response_variants)

    def create_response_variant(
        api_id: Annotated[str, "所属 API 记录的 ID（必填），可通过 list_mock_apis 获取"],
        response: Annotated[str, "变体响应体，JSON 字符串，如 '{\"code\":-1,\"msg\":\"error\"}'"] = '{}',
        name: Annotated[Optional[str], "变体名称，如 '成功响应'/'错误响应'/'超时响应'"] = None,
        enabled: Annotated[bool, "是否启用，True 启用 False 禁用"] = True,
        timeout: Annotated[int, "超时时间（毫秒），0 表示不限制"] = 0,
    ) -> OperationResultWithOptionalId:
      """
      为指定 Mock API 创建一个新的响应变体。

      用途：为同一个 mock 接口添加多种不同的模拟响应，例如成功响应、
           错误响应、超时响应等。变体创建后会自动绑定到所属 API 的
           变体列表中。

      场景：当需要模拟接口在不同条件下返回不同响应时调用。
           例如先创建一个成功变体，再创建一个错误变体，
           通过 enabled 切换当前使用哪个响应。

      Args:
        api_id: 所属 API 记录的 ID（必填）
        response: 变体响应体，JSON 字符串（可选，默认 '{}'）
        name: 变体名称（可选）
        enabled: 是否启用（可选，默认 True）
        timeout: 超时时间，毫秒，0 表示不限制（可选，默认 0）

      Returns:
        dict:
        - success (bool): 是否创建成功
        - id (str | None): 新创建的变体 ID，可用于后续操作；失败时为 None
        - status_code (int): 状态码
        - status_msg (str): 结果描述
      """
      record: ApiResponseVariantInsertRecord = {
        'api_data_id': api_id,
        'response': response,
        'enabled': enabled,
        'timeout': timeout,
        'operator': 'MCP',
      }
      if name is not None:
        record['name'] = name
      db = MockDBCache.get(self.work_dir)
      return db.insert_variant(record)

    self.mcp.add_tool(create_response_variant)

    def update_response_variant(
        variant_id: Annotated[str, "要修改的变体 ID（必填），可通过 list_response_variants 获取"],
        name: Annotated[Optional[str], "新的变体名称"] = None,
        response: Annotated[Optional[str], "新的响应体，JSON 字符串"] = None,
        enabled: Annotated[Optional[bool], "是否启用，True 启用 False 禁用"] = None,
        timeout: Annotated[Optional[int], "超时时间（毫秒），0 表示不限制"] = None,
    ) -> OperationResult:
      """
      修改指定响应变体的配置（字段级合并，仅更新传入的字段）。

      用途：修改某个变体的名称、响应体、启用状态或超时时间。
           未传入的字段保持原值不变。不允许修改变体所属的 API。

      前置条件：需要先调用 list_response_variants 获取 variant_id。
      组合：修改后可调用 list_response_variants(api_id) 验证修改结果。

      Args:
        variant_id: 要修改的变体 ID（必填）
        name: 新的变体名称（可选）
        response: 新的响应体，JSON 字符串（可选）
        enabled: 是否启用（可选）
        timeout: 超时时间，毫秒，0 表示不限制（可选）

      Returns:
        {"success": bool} 表示修改成功或失败。
      """
      record: ApiResponseVariantRecord = {'id': variant_id, 'operator': 'MCP'}
      if name is not None:
        record['name'] = name
      if response is not None:
        record['response'] = response
      if enabled is not None:
        record['enabled'] = enabled
      if timeout is not None:
        record['timeout'] = timeout
      db = MockDBCache.get(self.work_dir)
      return db.update_variant(record)

    self.mcp.add_tool(update_response_variant)

    def delete_response_variant(
        variant_id: Annotated[str, "要删除的变体 ID（必填），可通过 list_response_variants 获取"],
    ) -> OperationResult:
      """
      删除指定的响应变体。

      用途：删除一个不再需要的响应变体，同时自动从所属 API 的
           变体绑定列表中移除。删除后该变体将不再可用。

      前置条件：需要先调用 list_response_variants 获取 variant_id。
      注意：删除操作不可恢复，请确认后再调用。

      Args:
        variant_id: 要删除的变体 ID（必填）

      Returns:
        {"success": bool} 表示删除成功或失败。
      """
      db = MockDBCache.get(self.work_dir)
      return db.delete_variant(variant_id)

    self.mcp.add_tool(delete_response_variant)

    def copy_response_variant(
        variant_id: Annotated[str, "源变体 ID（必填），可通过 list_response_variants 获取"],
        target_api_id: Annotated[str, "目标 API 记录的 ID（必填），源变体将被复制并绑定到此 API"],
    ) -> OperationResultWithOptionalId:
      """
      复制一个响应变体到指定的 API 上。

      用途：将已有的响应变体复制到另一个 mock 接口，方便快速创建
           相似的模拟响应。新变体的 enabled 固定为 False（默认不启用），
           不复制源变体的启用状态。名称会自动追加 '(副本)' 后缀。

      场景：当多个接口需要相似的错误响应时，可以先在一个接口上配置好，
           再复制到其他接口，避免重复手动创建。

      Args:
        variant_id: 源变体 ID（必填）
        target_api_id: 目标 API 记录的 ID（必填），可以是与源变体不同的 API

      Returns:
        dict:
        - success (bool): 是否复制成功
        - id (str | None): 新创建的变体 ID；失败时为 None
        - status_code (int): 状态码
        - status_msg (str): 结果描述
      """
      db = MockDBCache.get(self.work_dir)
      return db.copy_variant(variant_id, target_api_id)

    self.mcp.add_tool(copy_response_variant)

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
    app = self.mcp.streamable_http_app()
    app.routes.append(Route('/ping', lambda request: JSONResponse({'data': 'pong!'}), methods=['GET']))

    # 无控制台环境（mcp_log=False）下使用禁用 StreamHandler 的日志配置，
    # 避免 uvicorn DefaultFormatter 访问 sys.stdout.isatty() 报错
    if self.mcp_log:
      log_config = uvicorn.config.LOGGING_CONFIG
    else:
      log_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
          'default': {'class': 'logging.NullHandler'},
          'access': {'class': 'logging.NullHandler'},
          'error': {'class': 'logging.NullHandler'},
        },
        'loggers': {
          'uvicorn': {'handlers': ['default'], 'level': 'INFO', 'propagate': False},
          'uvicorn.error': {'handlers': ['error'], 'level': 'INFO', 'propagate': False},
          'uvicorn.access': {'handlers': ['access'], 'level': 'INFO', 'propagate': False},
        },
      }
    config = uvicorn.Config(app, host='127.0.0.1', port=self.port, log_level='info', log_config=log_config)
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
  mcp_log = config.get('mcp_log', True)
  server = McpServer(port=port, work_dir=work_dir, stop_event=stop_event, mcp_log=mcp_log)
  server.start_server()


# 启动 MCP 服务
def start_mcp_server(config: McpServerRunConfig, stop_event: Optional[EventType] = None) -> Process:
  """启动 MCP 服务子进程"""
  print('Start MCP Server')
  mcp_process = Process(target=run_mcp_server, args=(config, stop_event), name='mcp_server')
  mcp_process.start()
  print('MCP Server is running')
  return mcp_process
