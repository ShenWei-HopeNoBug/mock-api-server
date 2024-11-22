# -*- coding: utf-8 -*-
import re
import pandas as pd
from flask import Flask, request
import requests
import time
import os


# 检查和下载静态资源
def check_static():
  data = pd.read_excel('output.xlsx', sheet_name=0, engine='openpyxl')
  response_col = data['Response']
  assets_list = []
  for response in response_col:
    assets_exg = re.compile(r'"(https?://[-/a-zA-Z0-9_.]*\.(?:png|jpg|jpeg|gif|avif|webp))"', re.IGNORECASE)
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


# 启本地 mock 服务
def start_server():
  data = pd.read_excel('output.xlsx', sheet_name=0, engine='openpyxl')

  app = Flask(__name__, static_folder='static', static_url_path='/static')

  # 常规接口
  @app.route('/api/<path:path>', methods=['GET', 'POST'])
  def request_api(path):
    method = request.method
    args = dict(request.args) or {}
    print(method, args)
    url_col = data['Url']
    for i, url in enumerate(url_col):
      if url.replace(r'https://dream.aimiai.com/', '') == path:
        return data['Response'][i]

  # 静态资源目录
  @app.route('/static/<path:path>', methods=['GET'])
  def send_static(path):
    return app.send_static_file(path)

  app.run()


if __name__ == '__main__':
  print('>' * 20, '开始检查和下载静态资源...')
  # 检查和下载静态资源
  check_static()

  print('>' * 20, '本地 mock 服务启动...')
  # 启本地 mock 服务
  start_server()
