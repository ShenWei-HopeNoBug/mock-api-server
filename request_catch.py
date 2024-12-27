# -*- coding: utf-8 -*-
from mitmproxy import http
from mitmproxy.tools.main import mitmdump
import re
import pandas as pd
from utils import create_md5, JsonFormat, find_connection_process

# 请求的 base_url
request_base_url = r'dream.aimiai.com/dream-plus'
# request_base_url = r'avatar-test.aicubes.cn/dream-plus'


# 处理请求抓包工具类
class RequestRecorder:
  def __init__(self, use_history=True):
    # 抓包数据保存路径
    self.save_path = './output.json'
    # self.save_path = './test/output.json'

    # 抓包缓存数据 dict
    self.response_catch_dict = {}

    # 以历史数据为基础继续抓包
    if use_history:
      self.init_response_catch_dict()

  # 读取本地保存数据初始化抓包缓存 dict
  def init_response_catch_dict(self):
    data = pd.read_json(self.save_path)
    fieldnames = ["Type", "Url", "Method", "Params", "Response"]

    self.response_catch_dict = {}
    # 行遍历
    for row_index, row_data in data.iterrows():
      record = {}
      for key in fieldnames:
        record[key] = row_data.get(key)
      self.__save_response(record)

  # 接口返回
  def response(self, flow: http.HTTPFlow):
    url = flow.request.url
    # 请求检查
    if not self.__check_response(flow.request, flow.response):
      print('不满足抓取条件：{}'.format(url))
      return

    # 请求链接
    method = flow.request.method

    # 请求参数，统一用 json string
    params = JsonFormat.format_dict_to_json_string({})

    request_content_type = flow.request.headers.get('content-type') or ''
    if method == 'POST':
      if 'application/x-www-form-urlencoded' in request_content_type:
        params = flow.request.form
      elif 'application/json' in request_content_type:
        params = flow.request.get_text()
    elif method == 'GET':
      params = JsonFormat.format_dict_to_json_string(dict(flow.request.query.copy()))

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
    self.__save_response(record)

  # 抓包结束
  def done(self):
    print('mitmproxy done!')
    fieldnames = ["Type", "Url", "Method", "Params", "Response"]
    data = {}
    for name in fieldnames:
      data[name] = []

    for response_data in self.response_catch_dict.values():
      for record in response_data.values():
        # 将数据存入对应列
        for key, value in record.items():
          if key in data:
            data[key].append(value)

    df = pd.DataFrame(data)

    # 将DataFrame写入Excel文件，每行为一个数据
    df.to_json(self.save_path)
    self.response_catch_dict = {}

  # 检查请求是否需要被抓取保存
  @staticmethod
  def __check_response(request, response):
    # 请求链接
    url = request.url

    # 需要排除的请求
    except_reg = re.compile(r'\.(png|jpg|jpeg|gif|avif|webp|js|css|ico|ttf|html|xml)')
    if except_reg.search(url):
      return False

    # 需要包含的请求
    include_reg = re.compile(request_base_url)
    if not include_reg.search(url):
      return False

    response_content_type = response.headers.get('Content-Type') or ''
    # 忽略 json 以外的响应内容
    if 'application/json' not in response_content_type:
      return False

    return True

  # 保存抓包数据到缓存
  def __save_response(self, record):
    secret_key = r'{}{}'.format(record['Method'], record['Params'])
    md5_key = create_md5(secret_key)
    search_key = r'{}{}'.format(record['Url'], record['Method'])
    # 创建新 url 的答案映射 dict
    if search_key not in self.response_catch_dict:
      self.response_catch_dict[search_key] = {}

    # 添加新的请求 response 内容
    self.response_catch_dict[search_key][md5_key] = record


class MitmdumpServer:
  def __init__(self):
    self.port = 8080

  # 启动抓包服务
  def start_server(self, port=8080):
    print('>' * 10, '抓包服务启动...', port)
    self.port = port
    mitmdump(['-s', __file__, '-p {}'.format(self.port)])

  # 关闭抓包服务
  def stop_server(self):
    process_list = find_connection_process(ip='0.0.0.0', port=self.port)
    if len(process_list) == 0:
      print('未找到 mitmdump server 进程！')

    for proc in process_list:
      proc.terminate()
      print('关闭 mitmdump server 成功!', proc)


addons = [
  # RequestRecorder(use_history=True)
  RequestRecorder(use_history=False)
]

if __name__ == '__main__':
  mitmdump_server = MitmdumpServer()
  mitmdump_server.start_server(port=8080)
