# -*- coding: utf-8 -*-
import re
import psutil
import pandas as pd
import requests
import time
import os
from utils import (
  JsonFormat,
  create_md5,
  remove_url_domain,
  check_and_create_dir,
)

import json
from flask import Flask, request
from flask_cors import CORS
import threading

class MockServer:
  def __init__(self):
    self.api_dict_path = './api_dict.json'
    self.api_data_path = './output.xlsx'
    self.static_host = 'http://127.0.0.1:5000'
    self.static_url_path = '/static'
    self.static_match_excepts = ['.png', '.jpg', '.jpeg', '.gif', '.avif', '.webp', '.npy']
    self.app = None

    pattern = r'(https?://[-/a-zA-Z0-9_.]*(?:{}))'.format('|'.join(self.static_match_excepts))
    # 静态资源正则匹配配置
    self.static_match_config = {
      # 匹配的正则实例
      "compare": re.compile(pattern, flags=re.IGNORECASE),
      # 静态资源要将 domain 替换的的基础 url 路径
      "domain": self.static_host,
      "static_url_path": self.static_url_path,
    }

  # 检查和下载静态资源
  def check_static(self):
    print('>' * 20, '开始检查和下载静态资源...')

    data = pd.read_excel(self.api_data_path, sheet_name=0, engine='openpyxl')
    response_col = data['Response']
    assets_list = []
    # 提取静态资源链接
    for response in response_col:
      assets_reg = self.static_match_config['compare']
      assets = assets_reg.findall(response)
      assets_list.extend(assets)

    # 去重
    assets_list = list(set(assets_list))

    # 静态资源目录
    assets_dir = '.{}'.format(self.static_url_path)
    # 创建静态资源文件夹
    check_and_create_dir(assets_dir)

    assets_length = len(assets_list)
    for i, assets in enumerate(assets_list):
      file_name = assets.split('/')[-1]

      # 拼接图片存放地址和名字
      assets_path = '{}/{}'.format(assets_dir, file_name)

      # 校验下载的文件是否已经存在
      if os.path.exists(assets_path):
        continue

      print('{}/{} 正在下载：{}'.format(i + 1, assets_length, assets))
      # 下载静态资源
      assets_data = requests.get(url=assets, timeout=30).content

      # 将图片写入指定位置
      with open(assets_path, 'wb') as fl:
        fl.write(assets_data)

      time.sleep(1)

  # 创建并保存 api_dict
  def create_api_dict(self):
    data = pd.read_excel(self.api_data_path, sheet_name=0, engine='openpyxl')
    assets_reg = self.static_match_config['compare']
    assets_base_url = '{}{}'.format(self.static_host, self.static_url_path)

    # 静态资源文本替换规则
    def assets_replace_method(match):
      assets_url = match[0]
      file_name = assets_url.split('/')[-1]

      return '{}/{}'.format(assets_base_url, file_name)

    api_dict = {}
    # 总行数
    for row_index, row_data in data.iterrows():
      response = row_data.get('Response')
      method = row_data.get('Method')
      params = row_data.get('Params')
      url = row_data.get('Url')

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
  def get_server_api_dict(self, read_catch=False):
    # 不读取缓存文件，重新生成一份 api_dict
    if not read_catch:
      return self.create_api_dict()

    # 本地不存在已经生成的 api 映射表，当场生成一份
    if not os.path.exists(self.api_dict_path):
      return self.create_api_dict()

    # 写入生成的 api 映射数据
    with open(self.api_dict_path, 'r', encoding='utf-8') as fl:
      data = fl.read()
      try:
        api_dict = json.loads(data)
        return api_dict
      except Exception as e:
        print('@@get_server_api_dict error', e)
        return self.create_api_dict()

  # 启动本地 mock 服务
  def start_server(self, read_catch=False):

    def callback():
      print('>' * 20, '本地 mock 服务启动...')

      api_dict = self.get_server_api_dict(read_catch)

      app = Flask(__name__, static_folder='static', static_url_path=self.static_url_path)
      self.app = app
      # 配置跨域
      CORS(app, resources={r"/static/*": {"origins": "*"}})

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
        if method == 'POST':
          if 'application/x-www-form-urlencoded' in request.headers.get('content-type'):
            params = request.form
          elif 'application/json' in request.headers.get('content-type'):
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

      # 静态资源目录
      @app.route('/static/<path:path>', methods=['GET'])
      def send_static(path):
        return app.send_static_file(path)

      app.run(host='0.0.0.0', port=5000, threaded=True)

    thread = threading.Thread(target=callback)
    thread.start()

  # 停止本地 mock 服务
  def stop_server(self):
    if self.app:
      connections = psutil.net_connections()
      for conn in connections:
        if conn.status == 'LISTEN':
          laddr = conn.laddr
          port = laddr.port
          ip = laddr.ip
          if port == 5000 and ip == '0.0.0.0':
            print(conn, conn.pid)
            proc = psutil.Process(conn.pid)
            print(proc)
            proc.terminate()

      self.app = None

  # 获取响应数据映射表键名
  @staticmethod
  def __get_response_dict_key(method, params):
    return create_md5('{}{}'.format(method, params))
