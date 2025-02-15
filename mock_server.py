# -*- coding: utf-8 -*-
import re
import pandas as pd
import requests
import time
import os
from decorate import create_thread
from utils import (
  JsonFormat,
  create_md5,
  remove_url_domain,
  check_and_create_dir,
  find_connection_process,
  compress_image,
  get_ip_address,
  get_mock_api_data_list,
)

import json
from flask import Flask, request
from flask_cors import CORS
import global_var


class MockServer:
  def __init__(self, work_dir='.', port=5000):
    # 工作目录相关配置
    self.work_dir = work_dir
    self.api_dict_path = '{}{}/api_dict.json'.format(work_dir, global_var.data_dir_path)
    self.api_data_path = '{}{}/output.json'.format(work_dir, global_var.data_dir_path)
    self.user_api_data_path = '{}{}/user_api.json'.format(work_dir, global_var.data_dir_path)
    self.mock_server_config_path = '{}{}/mock_server_config.json'.format(work_dir, global_var.config_dir_path)
    self.static_url_path = '/static'
    # ip 相关配置
    self.ip_address = get_ip_address()
    self.port = port
    # 静态资源相关配置
    self.static_host = 'http://{}:{}'.format(self.ip_address, self.port)
    # 包含的静态资源文件类型
    self.include_files = []

    # 工作目录文件检查
    self.check_work_dir_files()

    # 读取包含的静态资源文件类型
    with open(self.mock_server_config_path, 'r', encoding='utf-8') as fl:
      mock_server_config = json.loads(fl.read())
      self.include_files = mock_server_config.get('include_files', [])

    pattern = r'(https?://[-/a-zA-Z0-9_.]*(?:{}))'.format('|'.join(self.include_files))
    # 静态资源正则匹配配置
    self.static_match_config = {
      # 匹配的正则实例
      "compare": re.compile(pattern, flags=re.IGNORECASE),
      # 静态资源要将 domain 替换的的基础 url 路径
      "domain": self.static_host,
      "static_url_path": self.static_url_path,
    }

  # 检查工作目录文件完整性
  def check_work_dir_files(self):
    # 静态资源目录
    assets_dir = '{}{}'.format(self.work_dir, self.static_url_path)
    check_and_create_dir(assets_dir)

    # 存放数据的文件夹
    data_dir = '{}{}'.format(self.work_dir, global_var.data_dir_path)
    check_and_create_dir(data_dir)

    # 配置文件目录
    config_dir = '{}{}'.format(self.work_dir, global_var.config_dir_path)
    check_and_create_dir(config_dir)

    # 抓包数据文件不存在，创建一个
    if not os.path.exists(self.api_data_path):
      with open(self.api_data_path, 'w') as fl:
        fl.write('{}')

    # 用户手动配置 api 数据文件不存在，创建一个
    if not os.path.exists(self.user_api_data_path):
      with open(self.user_api_data_path, 'w') as fl:
        fl.write('[]')

  # 下载静态资源
  def download_static(self, compress=True):
    print('>' * 10, '开始检查和下载静态资源...')

    data = pd.read_json(self.api_data_path)
    response_col = data['response']
    assets_list = []
    # 提取静态资源链接
    for response in response_col:
      assets_reg = self.static_match_config['compare']
      assets = assets_reg.findall(response)
      assets_list.extend(assets)

    # 去重
    assets_list = list(set(assets_list))

    # 静态资源目录
    assets_dir = '{}{}'.format(self.work_dir, self.static_url_path)
    # 创建静态资源文件夹
    check_and_create_dir(assets_dir)

    download_assets = []
    # 检查需要下载的静态资源文件
    for asset in assets_list:
      client_exit = global_var.get_global_var(key='client_exit')
      # 程序已经全局退出，退出
      if client_exit:
        return

      file_name = asset.split('/')[-1]

      # 拼接图片存放地址和名字
      assets_path = '{}/{}'.format(assets_dir, file_name)
      if not os.path.exists(assets_path):
        download_assets.append(asset)

    assets_length = len(download_assets)
    for i, asset in enumerate(download_assets):
      client_exit = global_var.get_global_var(key='client_exit')
      # 程序已经全局退出，停止下载处理
      if client_exit:
        return

      file_name = asset.split('/')[-1]

      # 拼接图片存放地址和名字
      assets_path = '{}/{}'.format(assets_dir, file_name)

      # 校验下载的文件是否已经存在
      if os.path.exists(assets_path):
        continue

      print('{}/{} 正在下载：{}'.format(i + 1, assets_length, asset))
      # 下载静态资源
      try:
        response = requests.get(asset, timeout=30)
        if response.status_code != 200:
          print('下载失败：{}'.format(asset))
          continue
        assets_data = response.content

        # 将文件写入指定位置
        with open(assets_path, 'wb') as fl:
          fl.write(assets_data)

        # 压缩下载图片
        if compress:
          compress_image(
            input_path=assets_path,
            output_path=assets_path,
            quality=80
          )

        time.sleep(0.8)
      except Exception as e:
        print('下载静态资源出错！', e)

    print('下载静态资源完毕！')

  # 创建并保存 api_dict
  def create_api_dict(self):
    data = pd.read_json(self.api_data_path)
    assets_reg = self.static_match_config['compare']
    # 静态资源 base_url
    assets_base_url = '{}{}'.format(self.static_host, self.static_url_path)

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

      request_key = create_md5(remove_url_domain(url))
      # 响应数据查询键名
      response_key = self.__get_response_dict_key(
        method,
        JsonFormat.format_json_string(params),
      )

      # 创建 api 映射表
      if request_key not in api_dict:
        api_dict[request_key] = {}

      response = assets_reg.sub(assets_replace_method, response)
      api_dict[request_key][response_key] = json.loads(response)

    # 写入生成的 api 映射数据
    with open(self.api_dict_path, 'w', encoding='utf-8') as fl:
      fl.write(json.dumps(api_dict))

    return api_dict

  # 获取本地服务 api 数据字典
  def get_server_api_dict(self, read_cache=False):
    # 不读取缓存文件，重新生成一份 api_dict
    if not read_cache:
      return self.create_api_dict()

    # 本地不存在已经生成的 api 映射表，当场生成一份
    if not os.path.exists(self.api_dict_path):
      return self.create_api_dict()

    # 读取生成的 api 映射数据
    with open(self.api_dict_path, 'r', encoding='utf-8') as fl:
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
    app = Flask(__name__, static_folder='static', static_url_path=self.static_url_path, root_path=root_path)
    # 配置跨域(这个配置低版本的Flask加不加都一样)
    CORS(app, resources={r"/static/*".format(self.ip_address): {"origins": "*"}})

    @app.route('/system/shutdown', methods=['GET'])
    def server_shutdown():
      print('mock 服务收到 shutdown 指令！正在关闭服务...')
      self.stop_server()

    # 常规接口
    @app.route('/api/<path:path>', methods=['GET', 'POST'])
    def request_api(path):
      route = '/' + path
      request_key = create_md5(route)

      # 请求路径 mock 数据中不存在
      if request_key not in api_dict:
        return

      method = request.method

      params = JsonFormat.format_dict_to_json_string({})
      request_content_type = request.headers.get('content-type') or ''
      if method == 'POST':
        if 'application/x-www-form-urlencoded' in request_content_type:
          params = request.form
        elif 'application/json' in request_content_type:
          params = JsonFormat.format_json_string(request.get_data(as_text=True))
      elif method == 'GET':
        params = JsonFormat.format_dict_to_json_string(dict(request.args or {}))

      response_key = self.__get_response_dict_key(method, params)

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

  # 获取响应数据映射表键名
  @staticmethod
  def __get_response_dict_key(method, params):
    return create_md5('{}{}'.format(method, params))
