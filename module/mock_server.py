# -*- coding: utf-8 -*-
import time
import os
from config.work_file import (
  MOCK_SERVER_CONFIG_PATH,
  STATIC_DIR,
)
from config.default import (DEFAULT_HTTP_PARAMS_MATCH_MODE)
from config.enum import SERVER
from config.route import (STATIC_DELAY_ROUTE, SYSTEM_ROUTE, MOCK_API_ROUTE)
from lib.decorate import create_thread, error_catch
from lib.download_lib import get_static_match_regexp
from lib.logger_lib import APP_LOGGER
from lib.work_file_lib import create_work_files
from lib.app_lib import get_mock_api_data_list
from lib.db_lib import MockDBCache
from lib.utils_lib import (
  JsonFormat,
  create_md5,
  remove_url_domain,
  remove_url_query,
  get_ip_address,
  is_file_request,
  remove_byte_empty_content,
  shutdown_local_server,
  is_local_server_running,
)

import json
import re
import threading
from collections import OrderedDict
from typing import List, Pattern, Union
from app_types.db_types import ApiData
from app_types.mock_server_types import MockApiDict
from flask import (Flask, request, send_from_directory, jsonify)
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
    # http 请求参数匹配模式
    self.http_params_match_mode: int = DEFAULT_HTTP_PARAMS_MATCH_MODE

    # -------------------
    # 初始化
    # -------------------
    self.init()

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
      self.http_params_match_mode = mock_server_config.get(
        'http_params_match_mode',
        DEFAULT_HTTP_PARAMS_MATCH_MODE,
      )

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

  # 创建并保存 api_dict
  def create_api_dict(self) -> MockApiDict:
    """
    构建 mock api 映射表

    1. 准备静态资源替换规则：编译 include_files 正则，确定静态资源路由前缀（延时/非延时），
       定义替换回调，将响应中的原始静态资源 URL 重写为本地服务地址。
    2. 从 DB 加载全部 mock 数据，查询完毕后关闭 DB 连接（触发 checkpoint，释放文件锁）。
    3. 逐条遍历 mock 数据：
       - 用 API_INSERT_DEFAULTS 兜底缺失字段
       - 去掉 URL 域名得到路由，GET 请求额外去掉 query 参数
       - 由 route + method 生成 request_key，由 method + params 生成 response_key
       - 若配置了 include_files，对 response 做静态资源链接替换
       - 解析 response JSON 存入 api_dict[request_key][response_key]
    """
    assets_reg: Pattern[str] = get_static_match_regexp(self.include_files)
    # 区分是否延时两种静态资源的路由
    assets_route: str = STATIC_DELAY_ROUTE if self.static_load_speed > 0 else self.static_url_path
    # 静态资源 base_url
    assets_base_url: str = f'{self.static_host}{assets_route}'

    # 静态资源文本替换规则
    def assets_replace_method(match: re.Match) -> str:
      assets_url = match[0]
      file_name = assets_url.split('/')[-1]

      return f'{assets_base_url}/{file_name}'

    api_dict: MockApiDict = {}
    # 所有的 mock 数据列表（MITMPROXY 在前、USER 在后，各自按 created_at 旧→新排序）
    mock_api_data_list: List[ApiData] = get_mock_api_data_list(work_dir=self.work_dir)
    # 查询完毕，关闭 DB 连接（触发 checkpoint，释放文件锁）
    MockDBCache.close(work_dir=self.work_dir)
    # 行遍历
    for row_data in mock_api_data_list:
      data = {**SERVER.MOCK_API_DATA_DEFAULTS, **row_data}
      response: str = data['response']
      method: str = data['method']
      params: str = data['params']
      url: str = data['url']
      # 去掉域名
      route: str = remove_url_domain(url)
      # GET 请求去掉 query 参数
      if method == 'GET':
        route = remove_url_query(route)

      # 请求查询键名
      request_key: str = self.__get_request_dict_key(route, method)

      # 创建 api 映射表
      if request_key not in api_dict:
        api_dict[request_key] = {}

      try:
        # 响应数据查询键名
        response_key: str = self.__get_response_dict_key(
          method,
          self.__get_params_json_string(params),
        )
        # 替换静态资源链接
        if len(self.include_files):
          response = assets_reg.sub(assets_replace_method, response)
        api_dict[request_key][response_key] = json.loads(response)
      except (json.JSONDecodeError, TypeError) as e:
        print(f'mock 数据 JSON 解析失败，已跳过：\n - {method} {route} {params}\n - 错误：{e}')

    # 过滤掉所有 mock 数据均解析失败而残留的空字典，避免 request_api 取最后一条时 IndexError
    api_dict = {k: v for k, v in api_dict.items() if v}
    return api_dict

  # 启动本地 mock 服务
  @create_thread
  def start_server(self) -> None:
    print('>' * 10, '本地 mock 服务启动...')
    api_dict = self.create_api_dict()
    # 工作目录的绝对路径
    root_path: str = os.path.abspath(self.work_dir)
    static_folder: str = self.static_url_path.lstrip('/')
    app = Flask(__name__, static_folder=static_folder, static_url_path=self.static_url_path, root_path=root_path)

    # 配置跨域(/static静态资源文件夹在低版本的Flask加不加都一样)
    resources = {
      f"{self.static_url_path}/*": {"origins": "*"},
    }

    # 静态资源匹配缓存（按插入顺序保留，超出上限时淘汰最旧数据）
    static_match_cache: OrderedDict = OrderedDict()
    # 缓存上限，超出时清除最旧的数据
    static_match_cache_limit: int = 1000
    # 保护 static_match_cache 的 check-then-add 原子性，防止多线程并发请求同一文件时延时被执行多次
    static_match_lock = threading.Lock()

    # 动态匹配静态资源
    def static_match(path: str):
      route_path = '/' + path
      # 非文件请求，跳过
      if not is_file_request(route_path):
        return 'Not Found', 404

      # 文件名
      file_name: str = route_path.split('/')[-1]
      file_path: str = os.path.abspath(f'{self.work_dir}{self.static_url_path}/{file_name}')

      if not os.path.exists(file_path):
        return 'Not Found', 404

      search_key = create_md5(path)

      # 静态资源响应延时
      if self.static_load_speed > 0:
        # 加锁保证 check-then-add 原子性，延时 sleep 在锁外执行不阻塞其他文件请求
        with static_match_lock:
          already_cached = search_key in static_match_cache
          if not already_cached:
            static_match_cache[search_key] = True
            # 超出上限时淘汰最旧的数据
            if len(static_match_cache) > static_match_cache_limit:
              static_match_cache.popitem(last=False)

        if not already_cached:
          file_size: float = os.path.getsize(file_path) / 1024
          delay: float = file_size / self.static_load_speed

          # 限制最大延时时间
          max_delay: int = 120
          if delay > max_delay:
            delay = max_delay
          print(f'静态资源延时属性  文件大小：{file_size}KB  延时时间：{delay}s')
          time.sleep(delay)

      return send_from_directory(static_folder, file_name)

    # 批量注册静态资源匹配接口
    for static_route in self.static_match_route:
      # 配置路由合法性检查
      if not static_route.startswith('/'):
        continue

      # 为静态资源请求路由加跨域头
      resources[f"{static_route}/*"] = {"origins": "*"}
      # 创建静态资源请求接口
      app.route(f'{static_route}/<path:path>', methods=['GET'])(static_match)

    # 添加跨域头
    CORS(app, resources=resources)

    @app.route('/ping', methods=['GET'])
    def ping():
      return jsonify({'data': 'pong!'})

    # 服务进程自杀
    @app.route(f"{SYSTEM_ROUTE}/shutdown", methods=['GET'])
    def server_shutdown():

      @create_thread(daemon=True)
      def delayed_shutdown():
        APP_LOGGER.info('MOCK_SERVER 服务收到 shutdown 指令！正在关闭服务...')
        time.sleep(0.5)
        self.shutdown()

      delayed_shutdown()
      return jsonify({'data': 'shutting down'})

    # 统一 mock 匹配接口
    @app.route(f"{MOCK_API_ROUTE}/<path:path>", methods=['GET', 'POST'])
    def request_api(path):
      method = request.method
      route = '/' + path
      # GET 请求去掉 query 参数
      if method == 'GET':
        route = remove_url_query(route)

      # 请求查询键名
      request_key = self.__get_request_dict_key(route, method)
      # 请求路径 mock 数据中不存在
      if request_key not in api_dict:
        return jsonify({'error': 'Not Found'}), 404

      params = self.__get_params_json_string({})
      request_content_type = (request.headers.get('content-type') or '').lower()
      if method == 'POST':
        if 'application/x-www-form-urlencoded' in request_content_type:
          params = self.__get_params_json_string(request.form or {})
        elif 'application/json' in request_content_type:
          params = self.__get_params_json_string(request.get_data(as_text=True))
        elif 'multipart/form-data' in request_content_type:
          try:
            multipart_dict = dict(request.form or {})
            file = request.files.get('file')
            if file:
              content = remove_byte_empty_content(file.read())
              file_md5 = f'file-{create_md5(content)}'
              multipart_dict['file'] = file_md5
              print('params 存在 file 传参：', multipart_dict)
            params = self.__get_params_json_string(multipart_dict)
          except Exception as e:
            print('Mock Server 解析 multipart/form-data 传参异常', e)
            return jsonify({'error': 'multipart/form-data parse error'}), 404
        else:
          # 未识别的 content-type，无法提取参数，直接返回 404 避免误匹配空参数 mock 数据
          return jsonify({'error': 'Unsupported content-type'}), 404
      elif method == 'GET':
        params = self.__get_params_json_string(dict(request.args or {}))

      response_key = self.__get_response_dict_key(method, params)

      # 接口响应延时
      if self.response_delay > 0:
        print(f'接口响应延时：{self.response_delay}ms, route：{route}')
        time.sleep(self.response_delay / 1000)

      # 命中 mock 数据直接返回
      if response_key in api_dict[request_key]:
        response = api_dict[request_key][response_key]
        return jsonify(response)
      else:
        # 没命中 mock 数据，直接返回最后一条数据
        print(f'mock 数据命中失败：\n - {method} {route} {params}')
        if not api_dict[request_key]:
          return jsonify({'error': 'No valid mock data'}), 404
        last_response_key = list(api_dict[request_key].keys())[-1]
        return jsonify(api_dict[request_key][last_response_key])

    app.run(host='0.0.0.0', port=self.port, threaded=True)

  # 停止本地 mock 服务
  def shutdown(self) -> None:
    result = is_local_server_running(port=self.port, retry=2, retry_condition='NOT_RUNNING')
    if result:
      APP_LOGGER.info(f"即将关闭 MOCK_SERVER 服务！port={self.port}")
      shutdown_local_server(port=self.port)

  @error_catch(error_msg='__get_params_json_string 解析异常', error_return='{}')
  def __get_params_json_string(self, params: Union[dict, str]) -> str:
    """
    获取接口传参的 json 字符串
    将 dict 或 json str 统一序列化为标准 json 字符串
    用于生成 response_key 进行 mock 数据匹配
    精确匹配模式下对 key 排序，消除参数 key 顺序差异
    非精确模式仅做格式化
    """
    if isinstance(params, dict):
      # dict -> json str，精确模式下按 key 排序
      if self.http_params_match_mode == SERVER.HTTP_PARAMS_EXACT_MATCH:
        return JsonFormat.sort_dumps(params)
      else:
        return JsonFormat.dumps(params)
    elif isinstance(params, str):
      # json str -> 反序列化再序列化，精确模式下按 key 排序
      if self.http_params_match_mode == SERVER.HTTP_PARAMS_EXACT_MATCH:
        return JsonFormat.format_and_sort_json_string(params)
      else:
        return JsonFormat.format_json_string(params)
    else:
      # 非预期类型，返回空 json 字符串兜底
      return '{}'

  # 获取请求查询键名
  @staticmethod
  def __get_request_dict_key(route: str, method: str) -> str:
    return create_md5(f'{route}{method}')

  # 获取响应数据映射表键名
  @staticmethod
  def __get_response_dict_key(method: str, params: str) -> str:
    return create_md5(f'{method}{params}')
