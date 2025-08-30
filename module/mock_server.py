# -*- coding: utf-8 -*-
import time
import os
from config.work_file import (
  MOCK_SERVER_CONFIG_PATH,
  API_CACHE_DATA_PATH,
  STATIC_DIR,
)
from config.default import (DEFAULT_HTTP_PARAMS_MATCH_MODE)
from config.enum import SERVER
from config.route import (STATIC_DELAY_ROUTE, SYSTEM_ROUTE, MOCK_API_ROUTE)
from lib.decorate import create_thread
from lib.download_lib import get_static_match_regexp
from lib.work_file_lib import create_work_files
from lib.app_lib import get_mock_api_data_list
from lib.utils_lib import (
  JsonFormat,
  create_md5,
  remove_url_domain,
  remove_url_query,
  find_connection_process,
  get_ip_address,
  is_file_request,
)

import json
from flask import (Flask, request, send_from_directory)
from flask_cors import CORS


class MockServer:
  def __init__(self, work_dir='.', port=5000, response_delay=0, static_load_speed=0):
    # 工作目录相关配置
    self.work_dir = work_dir
    self.api_cache_path = r'{}{}'.format(work_dir, API_CACHE_DATA_PATH)
    self.static_url_path = STATIC_DIR
    # ip 相关配置
    self.ip_address = get_ip_address()
    self.port = port
    # 静态资源相关配置
    self.static_host = 'http://{}:{}'.format(self.ip_address, self.port)
    # 启动服务时解析的静态资源文件类型
    self.include_files = []
    # 动态匹配静态资源请求的路由
    self.static_match_route = []
    # 全局接口响应延时
    self.response_delay = response_delay
    # 全局静态资源请求加载速率
    self.static_load_speed = static_load_speed
    # http 请求参数匹配模式
    self.http_params_match_mode: int = DEFAULT_HTTP_PARAMS_MATCH_MODE

    # -------------------
    # 初始化
    # -------------------
    self.init()

  def init(self):
    # 工作目录文件检查
    create_work_files(self.work_dir)
    # 加载 mock 服务配置
    self.load_mock_server_config()

  # 加载 mock 服务配置
  def load_mock_server_config(self):
    mock_server_config_path = r'{}{}'.format(self.work_dir, MOCK_SERVER_CONFIG_PATH)

    # 读取服务配置
    with open(mock_server_config_path, 'r', encoding='utf-8') as fl:
      mock_server_config = json.loads(fl.read())
      include_files = mock_server_config.get('include_files', [])
      self.include_files = list(set(include_files))
      self.http_params_match_mode = mock_server_config.get(
        'http_params_match_mode',
        DEFAULT_HTTP_PARAMS_MATCH_MODE,
      )

      static_match_route = mock_server_config.get('static_match_route', [])
      static_match_route = list(set(static_match_route))
      # 内置已经占用命名的路由
      filter_route_list = [SYSTEM_ROUTE, MOCK_API_ROUTE, self.static_url_path]
      route_list = []
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
  def create_api_dict(self):
    assets_reg = get_static_match_regexp(self.include_files)
    # 区分是否延时两种静态资源的路由
    assets_route = STATIC_DELAY_ROUTE if self.static_load_speed > 0 else self.static_url_path
    # 静态资源 base_url
    assets_base_url = '{}{}'.format(self.static_host, assets_route)

    # 静态资源文本替换规则
    def assets_replace_method(match):
      assets_url = match[0]
      file_name = assets_url.split('/')[-1]

      return '{}/{}'.format(assets_base_url, file_name)

    api_dict = {}
    # 所有的 mock 数据列表
    mock_api_data_list = get_mock_api_data_list(work_dir=self.work_dir)
    # 行遍历
    for row_data in mock_api_data_list:
      response = row_data.get('response')
      method = row_data.get('method')
      params = row_data.get('params')
      url = row_data.get('url')
      # 去掉域名
      route = remove_url_domain(url)
      # GET 请求去掉 query 参数
      if method == 'GET':
        route = remove_url_query(route)

      # 请求查询键名
      request_key = self.__get_request_dict_key(route, method)
      # 响应数据查询键名
      response_key = self.__get_response_dict_key(
        method,
        self.__get_params_json_string(params),
      )

      # 创建 api 映射表
      if request_key not in api_dict:
        api_dict[request_key] = {}
      # 替换静态资源链接
      if len(self.include_files):
        response = assets_reg.sub(assets_replace_method, response)
      api_dict[request_key][response_key] = json.loads(response)

    # 写入生成的 api 映射数据
    with open(self.api_cache_path, 'w', encoding='utf-8') as fl:
      fl.write(JsonFormat.dumps(api_dict))

    return api_dict

  # 获取本地服务 api 数据字典
  def get_server_api_dict(self, read_cache=False):
    # 不读取缓存文件，重新生成一份 api_dict
    if not read_cache:
      return self.create_api_dict()

    # 本地不存在已经生成的 api 映射表，当场生成一份
    if not os.path.exists(self.api_cache_path):
      return self.create_api_dict()

    # 读取生成的 api 映射数据
    with open(self.api_cache_path, 'r', encoding='utf-8') as fl:
      data = fl.read()
      try:
        api_dict = json.loads(data)
        return api_dict
      except Exception as e:
        print('@@get_server_api_dict error', e)
        return self.create_api_dict()

  # 启动本地 mock 服务
  @create_thread
  def start_server(self, read_cache=False):
    print('>' * 10, '本地 mock 服务启动...')
    api_dict = self.get_server_api_dict(read_cache)
    # 工作目录的绝对路径
    root_path = os.path.abspath(self.work_dir)
    static_folder = self.static_url_path.lstrip('/')
    app = Flask(__name__, static_folder=static_folder, static_url_path=self.static_url_path, root_path=root_path)

    # 配置跨域(/static静态资源文件夹在低版本的Flask加不加都一样)
    resources = {
      r"{}/*".format(self.static_url_path): {"origins": "*"},
    }

    # 静态资源匹配缓存
    static_match_cache = set()

    # 动态匹配静态资源
    def static_match(path):
      route_path = '/' + path
      # 非文件请求，跳过
      if not is_file_request(route_path):
        return

      # 文件名
      file_name = route_path.split('/')[-1]
      file_path = os.path.abspath(r'{}{}/{}'.format(self.work_dir, self.static_url_path, file_name))

      if not os.path.exists(file_path):
        return

      search_key = create_md5(path)

      # 静态资源响应延时
      if (self.static_load_speed > 0) and (search_key not in static_match_cache):
        file_size = os.path.getsize(file_path) / 1024
        delay = file_size / self.static_load_speed

        # 限制最大延时时间
        max_delay = 120
        if delay > max_delay:
          delay = max_delay
        print('静态资源延时属性  文件大小：{}KB  延时时间：{}s'.format(file_size, delay))
        time.sleep(delay)
        static_match_cache.add(search_key)

      return send_from_directory(static_folder, file_name)

    # 批量注册静态资源匹配接口
    for static_route in self.static_match_route:
      # 配置路由合法性检查
      if not static_route.startswith('/'):
        continue

      # 为静态资源请求路由加跨域头
      resources[r"{}/*".format(static_route)] = {"origins": "*"}
      # 创建静态资源请求接口
      app.route('{}/<path:path>'.format(static_route), methods=['GET'])(static_match)

    # 添加跨域头
    CORS(app, resources=resources)

    # 服务进程自杀
    @app.route('{}/shutdown'.format(SYSTEM_ROUTE), methods=['GET'])
    def server_shutdown():
      print('mock 服务收到 shutdown 指令！正在关闭服务...')
      self.stop_server()

    # 统一 mock 匹配接口
    @app.route('{}/<path:path>'.format(MOCK_API_ROUTE), methods=['GET', 'POST'])
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
        return

      params = self.__get_params_json_string({})
      request_content_type = request.headers.get('content-type') or ''
      if method == 'POST':
        if 'application/x-www-form-urlencoded' in request_content_type:
          params = self.__get_params_json_string(request.form or {})
        elif 'application/json' in request_content_type:
          params = self.__get_params_json_string(request.get_data(as_text=True))
      elif method == 'GET':
        params = self.__get_params_json_string(dict(request.args or {}))

      response_key = self.__get_response_dict_key(method, params)

      # 接口响应延时
      if self.response_delay > 0:
        print('接口响应延时：{}ms, route：{}'.format(self.response_delay, route))
        time.sleep(self.response_delay / 1000)

      # 命中 mock 数据直接返回
      if response_key in api_dict[request_key]:
        response = api_dict[request_key][response_key]
        return response
      else:
        # 没命中 mock 数据，直接返回最后一条数据
        print('mock 数据命中失败：\n - {} {} {}'.format(method, route, params))
        last_response_key = list(api_dict[request_key].keys())[-1]
        return api_dict[request_key][last_response_key]

    app.run(host='0.0.0.0', port=self.port, threaded=True)

  # 停止本地 mock 服务
  def stop_server(self):
    process_list = find_connection_process(ip='0.0.0.0', port=self.port)
    if len(process_list) == 0:
      print('未找到 mock server 进程！port={}'.format(self.port))

    for proc in process_list:
      print('正在关闭 mock server 进程! port={}'.format(self.port), proc)
      proc.terminate()

  # 获取接口传参的 json 字符串
  def __get_params_json_string(self, params: dict or str) -> str:
    # 精确匹配模式下，对字典的 key 进行排序
    if type(params) == dict:
      # 传参数据为字典类型
      if self.http_params_match_mode == SERVER.HTTP_PARAMS_EXACT_MATCH:
        return JsonFormat.sort_dumps(params)
      else:
        return JsonFormat.dumps(params)
    elif type(params) == str:
      # 传参数据为字符串类型
      if self.http_params_match_mode == SERVER.HTTP_PARAMS_EXACT_MATCH:
        return JsonFormat.format_and_sort_json_string(params)
      else:
        return JsonFormat.format_json_string(params)
    else:
      return params

  # 获取请求查询键名
  @staticmethod
  def __get_request_dict_key(route: str, method: str) -> str:
    return create_md5('{}{}'.format(route, method))

  # 获取响应数据映射表键名
  @staticmethod
  def __get_response_dict_key(method: str, params: str):
    return create_md5('{}{}'.format(method, params))
