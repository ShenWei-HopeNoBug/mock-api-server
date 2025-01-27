# -*- coding: utf-8 -*-
import os
from mitmproxy import http
from mitmproxy.tools.main import mitmdump
import re
import pandas as pd
from utils import (create_md5, JsonFormat, find_connection_process, check_and_create_dir)
import global_var
import json


# 处理请求抓包工具类
class RequestRecorder:
  def __init__(self, use_history=True, work_dir='.'):
    # 工作目录
    self.work_dir = work_dir
    # 抓包服务 master 实例
    self.mitmproxy_master = None
    # 抓包结束标记
    self.mitmproxy_stop_signal = False
    # 抓包数据保存路径
    self.save_path = '{}{}/output.json'.format(work_dir, global_var.data_dir_path)
    self.mitmproxy_config_path = '{}{}/mitmproxy_config.json'.format(work_dir, global_var.config_dir_path)
    # 抓包缓存数据 dict
    self.response_catch_dict = {}
    # 抓包包含的 base_url
    self.include_path = ''

    # 检查工作目录文件完整性
    self.check_work_dir_files()

    with open(self.mitmproxy_config_path, 'r', encoding='utf-8') as fl:
      mitmproxy_config = json.loads(fl.read())
      self.include_path = mitmproxy_config.get('include_path', '')

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

  # 检查工作目录文件
  def check_work_dir_files(self):
    # 存放数据的文件夹
    data_dir = '{}{}'.format(self.work_dir, global_var.data_dir_path)
    check_and_create_dir(data_dir)

    # 配置文件目录
    config_dir = '{}{}'.format(self.work_dir, global_var.config_dir_path)
    check_and_create_dir(config_dir)

    # 抓包数据文件不存在，创建一个
    if not os.path.exists(self.save_path):
      with open(self.save_path, 'w') as fl:
        fl.write('{}')

    if not os.path.exists(self.mitmproxy_config_path):
      # 生成默认抓包配置文件
      with open(self.mitmproxy_config_path, 'w', encoding='utf-8') as fl:
        fl.write(json.dumps(global_var.mitmproxy_config))

  # 接口请求
  def request(self, flow: http.HTTPFlow):
    # 抓包结束，跳出
    if self.mitmproxy_stop_signal:
      return

    mitmproxy_stop_signal = global_var.get_global_var(key='mitmproxy_stop_signal')
    self.mitmproxy_stop_signal = mitmproxy_stop_signal
    # 收到结束抓包的信号，尝试关闭抓包服务
    if self.mitmproxy_master and mitmproxy_stop_signal:
      print('正在关闭 mitmproxy 服务...', flow.request.url)
      self.mitmproxy_master.shutdown()
      return

  # 接口返回
  def response(self, flow: http.HTTPFlow):
    # 抓包结束，跳出
    if self.mitmproxy_stop_signal:
      return

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
  def __check_response(self, request, response):
    # 请求链接
    url = request.url

    # 需要排除的请求
    except_reg = re.compile(r'\.(png|jpg|jpeg|gif|avif|webp|js|css|ico|ttf|html|xml)')
    if except_reg.search(url):
      return False

    # 需要包含的请求
    include_reg = re.compile(self.include_path)
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
  # mitmdump_server.stop_server()
  mitmdump_server.start_server(port=8080)
