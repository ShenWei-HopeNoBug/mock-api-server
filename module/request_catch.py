# -*- coding: utf-8 -*-
from mitmproxy import http
import re
from lib import mitmproxy_lib
from lib.work_file_lib import create_work_files
from config.work_file import (MITMPROXY_DATA_PATH, STATIC_DATA_PATH, MITMPROXY_CONFIG_PATH)
from lib.utils_lib import (JsonFormat, is_file_request, is_url_match)
from lib.system_lib import GLOBALS_CONFIG_MANAGER
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
    self.save_path = r'{}{}'.format(work_dir, MITMPROXY_DATA_PATH)
    self.static_save_path = r'{}{}'.format(work_dir, STATIC_DATA_PATH)
    self.mitmproxy_config_path = r'{}{}'.format(work_dir, MITMPROXY_CONFIG_PATH)
    # 抓包缓存数据 dict
    self.response_cache_dict = {}
    # 抓包包含的 path
    self.include_path: str or list = ''
    # 静态资源包含的 path
    self.static_include_path = []
    # 抓取静态资源缓存数据 dict
    self.static_cache_dict = {}

    # -------------------
    # 初始化
    # -------------------
    self.init(use_history)

  def init(self, use_history=True):
    # 检查工作目录文件完整性
    create_work_files(self.work_dir)
    # 加载抓包配置
    self.load_mitmproxy_config()

    # 以历史数据为基础继续抓包
    if use_history:
      self.load_history_cache()

  # 加载抓包配置
  def load_mitmproxy_config(self):
    with open(self.mitmproxy_config_path, 'r', encoding='utf-8') as fl:
      mitmproxy_config = json.loads(fl.read())
      self.include_path = mitmproxy_config.get('include_path', '')
      self.static_include_path = mitmproxy_config.get('static_include_path', [])

  # 读取本地保存数据初始化抓包数据
  def load_history_cache(self):
    # 加载 response 数据
    self.response_cache_dict = mitmproxy_lib.load_response_cache(self.save_path)
    # 加载静态资源数据
    self.static_cache_dict = mitmproxy_lib.load_static_cache(self.static_save_path)

  # 接口请求
  def request(self, flow: http.HTTPFlow):
    # 抓包结束，跳出
    if self.mitmproxy_stop_signal:
      return

    # 检查和保存静态资源的请求
    self.__check_and_save_static(flow)

    mitmproxy_stop_signal = GLOBALS_CONFIG_MANAGER.get(key='mitmproxy_stop_signal')
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
    params = JsonFormat.dumps({})

    request_content_type = flow.request.headers.get('content-type') or ''
    if method == 'POST':
      if 'application/x-www-form-urlencoded' in request_content_type:
        params = JsonFormat.dumps(dict(flow.request.urlencoded_form or {}))
      elif 'application/json' in request_content_type:
        params = flow.request.get_text()
      elif 'multipart/form-data' in request_content_type:
        print('content-type 为 multipart/form-data，请求参数不作保存：\n{}'.format(url))
    elif method == 'GET':
      params = JsonFormat.dumps(dict(flow.request.query.copy()))

    # 响应内容，统一用 json string
    response = flow.response.get_text()

    record = {
      "type": "MITMPROXY",
      "url": url,
      "method": method,
      "params": params,
      "response": response,
    }

    mitmproxy_lib.save_response_to_cache(record, self.response_cache_dict)

  # 抓包结束
  def done(self):
    print('mitmproxy done!')

    print('----> 正在保存抓包数据：', self.save_path)
    mitmproxy_lib.save_response(self.save_path, self.response_cache_dict)
    self.response_cache_dict = {}

    print('----> 正在保存静态资源数据：', self.static_save_path)
    mitmproxy_lib.save_static(self.static_save_path, self.static_cache_dict)
    self.static_cache_dict = {}

  # 检查请求是否需要被抓取保存
  def __check_response(self, request, response):
    # 请求链接
    url = request.url

    # 排除文件类型的请求
    if is_file_request(url):
      return False

    # 需要包含的请求
    if not is_url_match(url, self.include_path):
      return False

    response_content_type = response.headers.get('Content-Type') or ''
    # 忽略 json 以外的响应内容
    if 'application/json' not in response_content_type:
      return False

    return True

  # 检查和保存静态资源数据
  def __check_and_save_static(self, flow: http.HTTPFlow):
    url = flow.request.url
    # 非文件请求，跳过
    if not is_file_request(url):
      return

    # 检测链接内容是否符合配置
    if not is_url_match(url, self.static_include_path):
      return

    record = {
      "type": "MITMPROXY",
      "url": url,
    }
    mitmproxy_lib.save_static_to_cache(record, self.static_cache_dict)
