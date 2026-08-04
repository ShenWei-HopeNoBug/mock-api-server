# -*- coding: utf-8 -*-
import time
import os
from config.work_file import (
  MOCK_SERVER_CONFIG_PATH,
  STATIC_DIR,
)
from config.enum import SERVER
from config.route import (STATIC_DELAY_ROUTE, SYSTEM_ROUTE, MOCK_API_ROUTE)
from lib.decorate import create_thread, error_catch
from lib.logger_lib import APP_LOGGER
from lib.work_file_lib import create_work_files
from lib.app_lib import get_mock_api_data_list
from lib.server_lib import (
  AssetsReplaceFunc,
  ClientStateManager,
  MockRequestHandler,
  MockRequestParseError,
  StaticFileHandler,
  ThreadSafeLRUCache,
  create_assets_replace_func,
  parse_flask_request,
)
from lib.db import MockDBCache
from lib.utils_lib import (
  JsonFormat,
  create_md5,
  remove_url_domain,
  remove_url_query,
  get_ip_address,
  shutdown_local_server,
  is_local_server_running,
)
import json
from typing import Dict, List, Optional
from app_types.db_types import ApiData, ApiResponseVariant
from app_types.mock_server_types import (
  ClientStateResult,
  FlaskRouteResult,
  HttpMethod,
  MockApiEntry,
  MockApiMap,
  ParamsInput,
  ParamsJson,
  RequestContentTypeStr,
  RequestKey,
  ResponseKey,
  Route,
  VariantMeta,
)
from flask import (Flask, request, jsonify, make_response)
from flask_cors import CORS


class MockServer:
  def __init__(self, work_dir: str = '.', port: int = 5000, response_delay: int = 0, static_load_speed: int = 0):
    # 工作目录相关配置
    self.work_dir: str = work_dir
    self.static_url_path: str = STATIC_DIR
    # ip 相关配置
    self.ip_address: str = get_ip_address()
    self.port: int = port
    # 静态资源相关配置
    self.static_host: str = f'http://{self.ip_address}:{self.port}'
    # 启动服务时解析的静态资源文件类型
    self.include_files: List[str] = []
    # 动态匹配静态资源请求的路由
    self.static_match_route: List[str] = []
    # 全局接口响应延时
    self.response_delay: int = response_delay
    # 全局静态资源请求加载速率
    self.static_load_speed: int = static_load_speed
    # 客户端状态管理器
    self.client_state_manager: ClientStateManager = ClientStateManager(
      limit=SERVER.DEVICE_STATE_LIMIT
    )
    # -------------------
    # 初始化
    # -------------------
    self.init()

    # 静态资源替换函数：配置确定后一次性构造，避免 start_server 重复构建
    self.replace_assets: Optional[AssetsReplaceFunc] = create_assets_replace_func(
      include_files=self.include_files,
      static_host=self.static_host,
      static_url_path=self.static_url_path,
      static_load_speed=self.static_load_speed,
    )

  def init(self) -> None:
    # 工作目录文件检查
    create_work_files(self.work_dir)
    # 加载 mock 服务配置
    self.load_mock_server_config()

  # 加载 mock 服务配置
  def load_mock_server_config(self) -> None:
    mock_server_config_path = f'{self.work_dir}{MOCK_SERVER_CONFIG_PATH}'

    # 读取服务配置
    with open(mock_server_config_path, 'r', encoding='utf-8') as fl:
      mock_server_config = json.loads(fl.read())
      include_files: List[str] = mock_server_config.get('include_files', [])
      self.include_files = list(set(include_files))
      static_match_route: List[str] = mock_server_config.get('static_match_route', [])
      static_match_route = list(set(static_match_route))
      # 内置已经占用命名的路由
      filter_route_list: List[str] = [SYSTEM_ROUTE, MOCK_API_ROUTE, self.static_url_path]
      route_list: List[str] = []
      # 去除内部已经占用的路由
      for route in static_match_route:
        valid = True
        for filter_route in filter_route_list:
          if route.startswith(filter_route):
            valid = False
            break
        if valid:
          route_list.append(route)

      # 如果设置了静态资源返回延时，添加内置延时动态匹配路由
      if self.static_load_speed > 0:
        route_list.extend(STATIC_DELAY_ROUTE)

      self.static_match_route = route_list

  # 创建并保存 mock_api_map
  def create_api_map(self) -> MockApiMap:
    """
    构建 mock api 轻量匹配映射

    1. 从 DB 加载全部启用状态的 mock 数据；
    2. 逐条遍历，按 api_data 启用的变体列表构建元数据；
    3. 生成 request_key -> response_key -> ApiMatchMeta 的匹配映射；
    4. 不加载 response 文本，不解析 JSON，不关闭 DB，响应体由 MockRequestHandler 按需加载。
    """
    mock_api_map: MockApiMap = {}
    # 所有的 mock 数据列表（MITMPROXY 在前、USER 在后，各自按 created_at 旧→新排序，仅启用状态）
    mock_api_data_list: List[ApiData] = get_mock_api_data_list(work_dir=self.work_dir, enabled=True)

    mock_db = MockDBCache.get(self.work_dir)

    for row_data in mock_api_data_list:
      data = {**SERVER.MOCK_API_DATA_DEFAULTS, **row_data}
      api_data_id: str = data['id']
      method: str = data['method']
      params: str = data['params']
      request_content_type: str = data.get('request_content_type', 'NONE')
      url: str = data['url']
      # 去掉域名
      route: str = remove_url_domain(url)
      # GET 请求去掉 query 参数
      if method == 'GET':
        route = remove_url_query(route)

      # 请求查询键名
      request_key: str = self.__get_request_dict_key(route, method, request_content_type)

      # 创建 api 匹配映射
      if request_key not in mock_api_map:
        mock_api_map[request_key] = {}

      try:
        # 响应数据查询键名
        response_key: str = self.__get_response_dict_key(
          method,
          request_content_type,
          self.__get_params_json_string(params),
        )

        # 获取启用的变体元数据列表（按 response_variant_ids 顺序）
        variants: List[ApiResponseVariant] = mock_db.get_variants_by_api_id(api_data_id, enabled=True)
        variant_metas: List[VariantMeta] = [
          {'id': v['id'], 'timeout': v['timeout']}
          for v in variants
        ]

        mock_api_map[request_key][response_key] = {
          'api_data_id': api_data_id,
          'timeout': data['timeout'],
          'variants': variant_metas,
        }
      except Exception as e:
        print(f'mock 数据匹配映射构建失败，已跳过：\n - {method} {route} {params}\n - 错误：{e}')

    # 过滤掉所有 mock 数据均处理失败而残留的空字典
    mock_api_map = {k: v for k, v in mock_api_map.items() if v}
    return mock_api_map

  # 启动本地 mock 服务
  @create_thread
  def start_server(self) -> None:
    print('>' * 10, '本地 mock 服务启动...')
    mock_api_map: MockApiMap = self.create_api_map()

    root_path: str = os.path.abspath(self.work_dir)
    static_folder: str = self.static_url_path.lstrip('/')
    app: Flask = Flask(
      __name__,
      static_folder=static_folder,
      static_url_path=self.static_url_path,
      root_path=root_path,
    )

    # 配置跨域
    resources: Dict[str, Dict[str, str]] = {
      f"{self.static_url_path}/*": {"origins": "*"},
    }

    cache: ThreadSafeLRUCache[bool] = ThreadSafeLRUCache(limit=SERVER.STATIC_MATCH_CACHE_LIMIT)
    static_handler: StaticFileHandler = StaticFileHandler(
      work_dir=self.work_dir,
      static_url_path=self.static_url_path,
      static_load_speed=self.static_load_speed,
      static_folder=static_folder,
      cache=cache,
      max_delay=SERVER.STATIC_MATCH_MAX_DELAY_SECONDS,
    )

    response_cache: ThreadSafeLRUCache[MockApiEntry] = ThreadSafeLRUCache(limit=SERVER.RESPONSE_CACHE_LIMIT)

    mock_handler: MockRequestHandler = MockRequestHandler(
      mock_api_map=mock_api_map,
      work_dir=self.work_dir,
      response_cache=response_cache,
      response_delay=self.response_delay,
      get_request_key=self.__get_request_dict_key,
      get_response_key=self.__get_response_dict_key,
      replace_assets=self.replace_assets,
    )

    for static_route in self.static_match_route:
      if not static_route.startswith('/'):
        continue
      resources[f"{static_route}/*"] = {"origins": "*"}
      app.route(f'{static_route}/<path:path>', methods=['GET'])(static_handler.match)

    @app.route('/ping', methods=['GET'])
    def ping() -> FlaskRouteResult:
      return jsonify({'data': 'pong!'})

    @app.route(f"{SYSTEM_ROUTE}/shutdown", methods=['GET'])
    def server_shutdown() -> FlaskRouteResult:
      @create_thread(daemon=True)
      def delayed_shutdown() -> None:
        APP_LOGGER.info('MOCK_SERVER 服务收到 shutdown 指令！正在关闭服务...')
        time.sleep(0.5)
        self.shutdown()

      delayed_shutdown()
      return jsonify({'data': 'shutting down'})

    @app.route(f"{MOCK_API_ROUTE}/<path:path>", methods=['GET', 'POST'])
    def request_api(path: str) -> FlaskRouteResult:
      try:
        method, route, request_content_type, params = parse_flask_request(
          request, path, self.__get_params_json_string
        )
      except MockRequestParseError as e:
        return jsonify({'error': e.message}), 404

      device_id: str = (request.headers.get(SERVER.DEVICE_ID_HEADER, '').strip())[:128]

      state_result: Optional[ClientStateResult] = None
      if device_id:
        state_result = self.client_state_manager.get_or_create(device_id)

      result = mock_handler.handle(
        method, route, request_content_type, params, state_result=state_result
      )

      return make_response(result)

    CORS(app, resources=resources)
    app.run(host='0.0.0.0', port=self.port, threaded=True)

  # 停止本地 mock 服务
  def shutdown(self) -> None:
    result = is_local_server_running(
      port=self.port,
      retry=2,
      retry_condition='NOT_RUNNING',
      caller='MOCK_SERVER_SHUTDOWN',
    )
    if result:
      APP_LOGGER.info(f"即将关闭 MOCK_SERVER 服务！port={self.port}")
      shutdown_local_server(port=self.port)

  @error_catch(error_msg='__get_params_json_string 解析异常', error_return='{}')
  def __get_params_json_string(self, params: ParamsInput) -> ParamsJson:
    """
    获取接口传参的 json 字符串
    将 dict 或 json str 统一序列化为标准 json 字符串
    用于生成 response_key 进行 mock 数据匹配
    对 key 排序，消除参数 key 顺序差异
    """
    if isinstance(params, dict):
      return JsonFormat.sort_dumps(params)
    elif isinstance(params, str):
      return JsonFormat.format_and_sort_json_string(params)
    else:
      # 非预期类型，返回空 json 字符串兜底
      return '{}'

  # 获取请求查询键名
  @staticmethod
  def __get_request_dict_key(
      route: Route,
      method: HttpMethod,
      request_content_type: RequestContentTypeStr,
  ) -> RequestKey:
    return create_md5('{}-{}-{}'.format(route, method, request_content_type))

  # 获取响应数据映射表键名
  @staticmethod
  def __get_response_dict_key(
      method: HttpMethod,
      request_content_type: RequestContentTypeStr,
      params: ParamsJson,
  ) -> ResponseKey:
    return create_md5('{}-{}-{}'.format(method, request_content_type, params))
