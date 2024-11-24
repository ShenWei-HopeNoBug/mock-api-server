# -*- coding: utf-8 -*-
from mitmproxy import http
import re
import pandas as pd
from utils import create_md5, format_dict


# 处理请求抓包工具类
class RequestRecorder:
  def __init__(self):
    self.response_map = {}

  def save_response(self, record):
    secret_key = r'{}{}'.format(record['Method'], record['Params'])
    md5_key = create_md5(secret_key)
    search_key = r'{}{}'.format(record['Url'], record['Method'])
    # 创建新 url 的答案映射 dict
    if search_key not in self.response_map:
      self.response_map[search_key] = {}

    # 添加新的请求 response 内容
    self.response_map[search_key][md5_key] = record

  def response(self, flow: http.HTTPFlow):
    # 请求链接
    url = flow.request.url

    # 需要排除的请求
    exg_except = re.compile(r'\.(png|jpg|jpeg|gif|avif|webp|js|css)')
    if exg_except.search(url):
      return
    # 需要包含的请求
    exg_include = re.compile(r'dream.aimiai.com')
    if not exg_include.search(url):
      return

    method = flow.request.method
    params = {}
    if method == 'POST':
      if 'application/x-www-form-urlencoded' in flow.request.headers.get('content-type'):
        params = flow.request.form
      elif 'application/json' in flow.request.headers.get('content-type'):
        params = flow.request.text
    elif method == 'GET':
      params = dict(flow.request.query or {})

    # 响应内容
    response = str(flow.response.content, encoding="utf-8")

    '''
    @todo 这里 GET 请求保存的 json 数据引号是单引导，解析会有问题，需要处理下
    '''
    record = {
      "Type": "PACKAGE_CATCH",
      "Url": url,
      "Method": method,
      "Params": format_dict(params),
      "Response": response,
    }

    # 保存请求映射
    self.save_response(record)

  def done(self):
    fieldnames = ["Type", "Url", "Method", "Params", "Response"]
    data = {}
    for name in fieldnames:
      data[name] = []

    for response_data in self.response_map.values():
      for record in response_data.values():
        for key, value in record.items():
          if key in data:
            data[key].append(value)

    df = pd.DataFrame(data)

    # 将DataFrame写入Excel文件，每行为一个数据
    df.to_excel('output.xlsx', index=False, engine='openpyxl')
    self.response_map = {}


addons = [
  RequestRecorder()
]
