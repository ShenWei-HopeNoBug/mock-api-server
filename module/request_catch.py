# -*- coding: utf-8 -*-
import json
import os
from typing import Dict, List, Optional, Union
from multiprocessing.synchronize import Event as EventType
from mitmproxy import http
from app_types.db_types import ApiRecord
from app_types.mitmproxy_types import (
  MitmproxyConfig,
  ResponseCacheDict,
  StaticCacheDict,
  StaticRecord,
)
from mitmproxy.tools.dump import DumpMaster
from config.work_file import (
  MITMPROXY_CONFIG_PATH,
  DB_DATA_PATH,
)
from lib import mitmproxy_lib
from lib.db import MockDB
from lib.work_file_lib import create_work_files
from lib.utils_lib import (
  JsonFormat,
  is_file_request,
  is_url_match,
  get_multipart_dict,
  get_request_content_type,
)


# 处理请求抓包工具类
class RequestRecorder:
  def __init__(
      self,
      work_dir: str = '.',
      ready_event: Optional[EventType] = None,
      stop_event: Optional[EventType] = None
  ):
    # 工作目录
    self.work_dir: str = work_dir
    # SQLite 数据库路径
    self.db_path: str = f'{work_dir}{DB_DATA_PATH}'
    # MockDB 实例
    self.mock_db: MockDB = MockDB(self.db_path)
    # 抓包服务 master 实例
    self.mitmproxy_master: Optional[DumpMaster] = None
    # 就绪信号 Event（跨进程，running 钩子触发后通知父进程服务已启动完毕）
    self.ready_event: Optional[EventType] = ready_event
    # 停止信号 Event（跨进程，由外部轮询任务负责触发 master.shutdown）
    self.stop_event: Optional[EventType] = stop_event
    # 抓包结束标记
    self.mitmproxy_stop_signal: bool = False
    # 抓包缓存数据 dict
    # 结构: {search_key: {md5_key: ApiRecord, ...}, ...}
    self.response_cache_dict: ResponseCacheDict = {}
    # 抓包包含的 path（正则字符串或正则字符串列表）
    self.include_path: Union[str, List[str]] = ''
    # 静态资源包含的 path（正则字符串列表）
    self.static_include_path: List[str] = []
    # 抓取静态资源缓存数据 dict
    # 结构: {md5_key: StaticRecord, ...}
    self.static_cache_dict: StaticCacheDict = {}

    # -------------------
    # 初始化
    # -------------------
    self.init()

  def init(self) -> None:
    # 检查工作目录文件完整性
    create_work_files(self.work_dir)
    # 加载抓包配置
    self.load_mitmproxy_config()

  # mitmproxy 代理服务完全启动后触发，通知父进程服务已就绪
  def running(self) -> None:
    if self.ready_event is not None:
      self.ready_event.set()

  # 加载抓包配置
  def load_mitmproxy_config(self) -> None:
    # 抓包配置文件路径
    mitmproxy_config_path: str = os.path.abspath(r'{}{}'.format(self.work_dir, MITMPROXY_CONFIG_PATH))
    with open(mitmproxy_config_path, 'r', encoding='utf-8') as fl:
      mitmproxy_config: MitmproxyConfig = json.loads(fl.read())
      self.include_path = mitmproxy_config.get('include_path', '')
      self.static_include_path = mitmproxy_config.get('static_include_path', [])

  # 接口请求
  def request(self, flow: http.HTTPFlow) -> None:
    # 读取全局停止信号，收到信号后尝试关闭抓包服务并不再保存任何数据
    if self.__check_stop_signal():
      return

    # 检查和保存静态资源的请求
    self.__check_and_save_static(flow)

  # 接口返回
  def response(self, flow: http.HTTPFlow) -> None:
    # 读取全局停止信号，收到信号后尝试关闭抓包服务并不再保存任何数据
    if self.__check_stop_signal():
      return

    url: str = flow.request.url
    # 请求检查
    if not self.__check_response(flow.request, flow.response):
      print('不满足抓取条件：{}'.format(url))
      return

    # 请求链接
    method: str = flow.request.method

    # 请求参数，统一用 json string
    params: str = '{}'

    # 根据请求的 content-type 提取参数，统一转为 json string
    raw_content_type: str = (flow.request.headers.get('content-type') or '').lower()
    if method == 'POST':
      # 表单提交：键值对形式，直接转 dict
      if 'application/x-www-form-urlencoded' in raw_content_type:
        params = JsonFormat.dumps(dict(flow.request.urlencoded_form or {}))
      # JSON 请求体：原始文本可能是非标准 JSON，format_json_string 做容错格式化
      elif 'application/json' in raw_content_type:
        params_json: str = flow.request.get_text() or '{}'
        params = JsonFormat.format_json_string(params_json)
      # 文件上传：multipart 内可能含文件字段，get_multipart_dict 对 file 传参做特殊处理（提取文件名等）
      elif 'multipart/form-data' in raw_content_type:
        print('content-type 为 multipart/form-data，针对内部的 file 传参作特殊处理：\n{}'.format(url))
        multipart_dict: Dict[str, str] = get_multipart_dict(flow.request.multipart_form)
        params = JsonFormat.dumps(multipart_dict)
      # 其他 POST content-type（如 text/plain、application/xml 等）不提取参数，保持默认空对象
    elif method == 'GET':
      # GET 请求参数在 query string 中，直接转 dict
      params = JsonFormat.dumps(dict(flow.request.query.copy()))

    # 响应内容，统一用 json string
    # __check_response 已确保 flow.response 非空
    response: str = '{}' if not flow.response else flow.response.get_text() or '{}'

    request_content_type = get_request_content_type(raw_content_type, method)

    record: ApiRecord = {
      "type": "MITMPROXY",
      "url": url,
      "method": method,
      "request_content_type": request_content_type,
      "params": params,
      "response": response,
    }

    mitmproxy_lib.save_response_to_cache(record, self.response_cache_dict)

  # 抓包结束
  def done(self) -> None:
    print('mitmproxy done!')

    # 从 response_cache_dict 提取全部抓包记录
    # 缓冲结构: {search_key: {md5_key: ApiRecord, ...}, ...}
    records: List[ApiRecord] = []
    for response_data in self.response_cache_dict.values():
      for record in response_data.values():
        records.append(record)

    print('----> 正在保存抓包数据，共 {} 条'.format(len(records)))
    self.mock_db.batch_insert_api(records)
    self.response_cache_dict = {}

    # 从 static_cache_dict 提取全部静态资源 URL
    # 缓冲结构: {md5_key: StaticRecord, ...}
    urls: List[str] = [record.get('url', '') for record in self.static_cache_dict.values()]
    print('----> 正在保存静态资源数据，共 {} 条'.format(len(urls)))
    self.mock_db.batch_insert_static(urls)
    self.static_cache_dict = {}

    # 批量写入完成后关闭连接，触发 SQLite 自动 checkpoint 将 -wal 合并回主库
    # mitmproxy 进程为"用完即关"，运行期间不再访问 DB
    self.mock_db.close()

  # 检查停止信号，收到信号后不再保存任何数据（关闭职责由轮询任务负责）
  def __check_stop_signal(self) -> bool:
    if self.stop_event is not None and self.stop_event.is_set():
      self.mitmproxy_stop_signal = True
      return True
    return False

  # 检查请求是否需要被抓取保存
  def __check_response(self, request: http.Request, response: Optional[http.Response]) -> bool:
    # response 为空，跳过
    if response is None:
      return False

    # 请求链接
    url: str = request.url

    # 排除文件类型的请求
    if is_file_request(url):
      return False

    # 需要包含的请求
    if not is_url_match(url, self.include_path):
      return False

    response_content_type: str = response.headers.get('Content-Type') or ''
    # 忽略 json 以外的响应内容
    if 'application/json' not in response_content_type.lower():
      return False

    return True

  # 检查和保存静态资源数据
  def __check_and_save_static(self, flow: http.HTTPFlow) -> None:
    url: str = flow.request.url
    # 非文件请求，跳过
    if not is_file_request(url):
      return

    # 检测链接内容是否符合配置
    if not is_url_match(url, self.static_include_path):
      return

    record: StaticRecord = {
      "type": "MITMPROXY",
      "url": url,
    }
    mitmproxy_lib.save_static_to_cache(record, self.static_cache_dict)
