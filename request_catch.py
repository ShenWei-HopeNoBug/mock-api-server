# -*- coding: utf-8 -*-
from mitmproxy import http
import re
import pandas as pd
from utils import create_md5, format_dict_to_json_string


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
    except_reg = re.compile(r'\.(png|jpg|jpeg|gif|avif|webp|js|css|ico|ttf|html|xml)')
    if except_reg.search(url):
      return
    # 需要包含的请求
    include_reg = re.compile(r'dream.aimiai.com/dream-plus')
    if not include_reg.search(url):
      return

    method = flow.request.method

    # 请求参数，统一用 json string
    params = format_dict_to_json_string({})
    if method == 'POST':
      if 'application/x-www-form-urlencoded' in flow.request.headers.get('content-type'):
        params = flow.request.form
      elif 'application/json' in flow.request.headers.get('content-type'):
        params = flow.request.get_text()
    elif method == 'GET':
      params = format_dict_to_json_string(dict(flow.request.query.copy()))

    # 响应内容，统一用 json string
    response = flow.response.get_text()

    record = {
      "Type": "PACKAGE_CATCH",
      "Url": url,
      "Method": method,
      "Params": params,
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
        # 将数据存入对应列
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
