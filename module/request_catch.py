# -*- coding: utf-8 -*-
import json
import os
from mitmproxy import http
from mitmproxy.tools.dump import DumpMaster
from config.work_file import (
  MITMPROXY_CONFIG_PATH,
  DB_DATA_PATH,
)
from lib import mitmproxy_lib
from lib.db_lib import MockDB
from lib.work_file_lib import create_work_files
from lib.system_lib import GLOBALS_CONFIG_MANAGER
from lib.utils_lib import (
  JsonFormat,
  is_file_request,
  is_url_match,
  generate_uuid,
  get_multipart_dict,
)


# 处理请求抓包工具类
class RequestRecorder:
  def __init__(self, use_history=True, work_dir='.'):
    # 工作目录
    self.work_dir: str = work_dir
    # SQLite 数据库路径
    self.db_path: str = f'{work_dir}{DB_DATA_PATH}'
    # MockDB 实例
    self.mock_db: MockDB = MockDB(self.db_path)
    # 抓包服务 master 实例
    self.mitmproxy_master: DumpMaster or None = None
    # 抓包结束标记
    self.mitmproxy_stop_signal: bool = False
    # 抓包缓存数据 dict
    self.response_cache_dict: dict = {}
    # 抓包包含的 path
    self.include_path: str or list = ''
    # 静态资源包含的 path
    self.static_include_path: list = []
    # 抓取静态资源缓存数据 dict
    self.static_cache_dict: dict = {}

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
    # 抓包配置文件路径
    mitmproxy_config_path = os.path.abspath(r'{}{}'.format(self.work_dir, MITMPROXY_CONFIG_PATH))
    with open(mitmproxy_config_path, 'r', encoding='utf-8') as fl:
      mitmproxy_config = json.loads(fl.read())
      self.include_path = mitmproxy_config.get('include_path', '')
      self.static_include_path = mitmproxy_config.get('static_include_path', [])

  # 从 DB 加载历史数据初始化抓包缓存
  def load_history_cache(self):
    # 从 DB 加载历史 response 数据，填充内存缓冲用于抓包去重
    mitmproxy_data = self.mock_db.get_api_list(api_type='MITMPROXY')
    for row_data in mitmproxy_data:
      mitmproxy_lib.save_response_to_cache(row_data, self.response_cache_dict)

    # 从 DB 加载历史静态资源数据，填充内存缓冲用于去重
    static_data = self.mock_db.get_static_list()
    for row_data in static_data:
      mitmproxy_lib.save_static_to_cache(row_data, self.static_cache_dict)

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
    params: str = JsonFormat.dumps({})

    request_content_type = flow.request.headers.get('content-type') or ''
    if method == 'POST':
      if 'application/x-www-form-urlencoded' in request_content_type:
        params = JsonFormat.dumps(dict(flow.request.urlencoded_form or {}))
      elif 'application/json' in request_content_type:
        params_json: str = flow.request.get_text() or JsonFormat.dumps({})
        params = JsonFormat.format_json_string(params_json)
      elif 'multipart/form-data' in request_content_type:
        print('content-type 为 multipart/form-data，针对内部的 file 传参作特殊处理：\n{}'.format(url))
        multipart_dict = get_multipart_dict(flow.request.multipart_form)
        params = JsonFormat.dumps(multipart_dict)
    elif method == 'GET':
      params = JsonFormat.dumps(dict(flow.request.query.copy()))

    # 响应内容，统一用 json string
    response = flow.response.get_text()

    record = {
      "id": generate_uuid(),
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

    # 从 response_cache_dict 提取全部抓包记录
    # 缓冲结构: {search_key: {md5_key: record, ...}, ...}
    records = []
    for response_data in self.response_cache_dict.values():
      for record in response_data.values():
        records.append(record)

    print('----> 正在保存抓包数据，共 {} 条'.format(len(records)))
    '''
    @todo 这个地方要处理下 records，要把带 id 的数据去掉，抓包的时候如果有覆盖也要删除 id
    '''
    self.mock_db.batch_insert_api(records)
    self.response_cache_dict = {}

    # 从 static_cache_dict 提取全部静态资源 URL
    # 缓冲结构: {md5_key: record, ...}
    urls = [record.get('url') for record in self.static_cache_dict.values()]
    print('----> 正在保存静态资源数据，共 {} 条'.format(len(urls)))
    self.mock_db.batch_insert_static(urls)
    self.static_cache_dict = {}

    # 批量写入完成后关闭连接，触发 SQLite 自动 checkpoint 将 -wal 合并回主库
    # mitmproxy 进程为"用完即关"，运行期间不再访问 DB
    self.mock_db.close()

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
