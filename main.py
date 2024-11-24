# -*- coding: utf-8 -*-
import re
import pandas as pd
from flask import Flask, request
import requests
import time
import os
from utils import create_md5, remove_url_domain, format_json_string, format_dict_to_json_string
import json


class MockServer:
  def __init__(self):
    self.api_dict_path = './api_dict.json'
    self.api_data_path = './output.xlsx'

  # 检查和下载静态资源
  def check_static(self):
    data = pd.read_excel(self.api_data_path, sheet_name=0, engine='openpyxl')
    response_col = data['Response']
    assets_list = []
    for response in response_col:
      assets_exg = re.compile(r'(https?://[-/a-zA-Z0-9_.]*\.(?:png|jpg|jpeg|gif|avif|webp))', re.IGNORECASE)
      assets = assets_exg.findall(response)
      assets_list.extend(assets)

    assets_list = list(set(assets_list))
    assets_length = len(assets_list)
    for i, assets in enumerate(assets_list):
      file_name = assets.split('/')[-1]
      root = './static'
      # 拼接图片存放地址和名字
      img_path = '{}/{}'.format(root, file_name)

      # 校验下载的文件是否已经存在
      if os.path.exists(img_path):
        continue

      print('{}/{} 正在下载：{}'.format(i + 1, assets_length, assets))
      img_data = requests.get(url=assets).content

      # 将图片写入指定位置
      with open(img_path, 'wb') as fl:
        fl.write(img_data)

      time.sleep(1)

  # 创建并保存 api_dict
  def create_api_dict(self):
    data = pd.read_excel(self.api_data_path, sheet_name=0, engine='openpyxl')

    api_dict = {}
    # 总行数
    for row_index, row_data in data.iterrows():
      response = row_data.get('Response')
      method = row_data.get('Method')
      params = row_data.get('Params')
      url = row_data.get('Url')

      request_key = create_md5(remove_url_domain(url))
      response_key = self._get_response_dict_key(method, format_json_string(params))

      # 创建 api 映射表
      if request_key not in api_dict:
        api_dict[request_key] = {}

      '''
      @todo 这个地方需要把静态资源链接全部替换成本地 mock 的静态资源
      '''
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

  # 启本地 mock 服务
  def start_server(self):
    api_dict = self.get_server_api_dict()

    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # 常规接口
    @app.route('/api/<path:path>', methods=['GET', 'POST'])
    def request_api(path):
      route = '/' + path
      request_key = create_md5(route)

      # 请求路径 mock 数据中不存在
      if request_key not in api_dict:
        return

      method = request.method

      params = {}
      if method == 'POST':
        if 'application/x-www-form-urlencoded' in request.headers.get('content-type'):
          params = request.form
        elif 'application/json' in request.headers.get('content-type'):
          params = request.get_json()
      elif method == 'GET':
        params = dict(request.args or {})

      response_key = self._get_response_dict_key(
        method,
        format_dict_to_json_string(params),
      )

      '''
      @todo 这里需要处理下没命中 mock 数据的情况，直接返回最后一条 mock 数据
      '''

      # 命中 mock 数据直接返回
      if response_key in api_dict[request_key]:
        response = api_dict[request_key][response_key]
        return response

    # 静态资源目录
    @app.route('/static/<path:path>', methods=['GET'])
    def send_static(path):
      return app.send_static_file(path)

    app.run()

  # 获取响应数据映射表键名
  def _get_response_dict_key(self, method, params):
    return create_md5('{}{}'.format(method, params))


if __name__ == '__main__':
  mock_server = MockServer()

  # 检查和下载静态资源
  print('>' * 20, '开始检查和下载静态资源...')
  # mock_server.check_static()

  print('>' * 20, '本地 mock 服务启动...')
  # 启本地 mock 服务
  mock_server.start_server()
