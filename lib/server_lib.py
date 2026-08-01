# -*- coding: utf-8 -*-
import os
import time
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, Generic, List, Tuple, TypeVar, Union

from flask import Request, send_from_directory, jsonify

from lib.decorate import error_catch
from lib.db_lib import MockDBCache
from lib.utils_lib import (
  create_md5,
  get_request_content_type,
  is_file_request,
  remove_byte_empty_content,
  remove_url_query,
)
from app_types.app_gui_types import RequestContentType
from app_types.db_types import StaticData
from app_types.mock_server_types import (
  FlaskRouteResult,
  MockApiDict,
  MockApiEntry,
  ParsedRequest,
)


# 读取 static 数据
@error_catch(error_msg='读取 static 数据失败', error_return=[])
def get_static_data_list(work_dir: str = '.') -> List[StaticData]:
  mock_db = MockDBCache.get(work_dir)
  return mock_db.get_static_list()


T = TypeVar('T')


class StaticMatchCache(Generic[T]):
  """
  静态资源匹配缓存

  用于记录某个静态资源是否已经被请求过，从而保证延时只触发一次。
  基于 OrderedDict 实现 LRU 淘汰，配合 Lock 保证 check-then-add 的原子性。
  """

  def __init__(self, limit: int):
    self._limit: int = limit
    self._cache: 'OrderedDict[str, T]' = OrderedDict()
    self._lock: threading.Lock = threading.Lock()

  def mark(self, key: str, value: T) -> bool:
    """
    原子性 check-then-add：
    - 若 key 已存在，返回 False
    - 若 key 不存在，写入并返回 True
    """
    with self._lock:
      if key in self._cache:
        return False
      self._cache[key] = value
      if len(self._cache) > self._limit:
        self._cache.popitem(last=False)
      return True


class StaticFileHandler:
  """
  静态资源请求处理器

  负责根据 URL path 匹配本地静态资源文件，并支持按文件大小和加载速度计算延时。
  """

  def __init__(
      self,
      work_dir: str,
      static_url_path: str,
      static_load_speed: int,
      static_folder: str,
      cache: StaticMatchCache[bool],
      max_delay: Union[int, float],
  ) -> None:
    self.work_dir: str = work_dir
    self.static_url_path: str = static_url_path
    self.static_load_speed: int = static_load_speed
    self.static_folder: str = static_folder
    self.cache: StaticMatchCache[bool] = cache
    self.max_delay: Union[int, float] = max_delay

  def match(self, path: str) -> FlaskRouteResult:
    """匹配并返回本地静态资源文件"""
    route_path: str = '/' + path
    # 非文件请求，跳过
    if not is_file_request(route_path):
      return 'Not Found', 404

    file_name: str = route_path.split('/')[-1]
    file_path: str = os.path.abspath(f'{self.work_dir}{self.static_url_path}/{file_name}')

    if not os.path.exists(file_path):
      return 'Not Found', 404

    search_key: str = create_md5(path)

    # 静态资源响应延时
    if self.static_load_speed > 0:
      is_first: bool = self.cache.mark(search_key, True)
      if is_first:
        file_size: float = os.path.getsize(file_path) / 1024
        delay: float = file_size / self.static_load_speed
        if delay > self.max_delay:
          delay = self.max_delay
        print(f'静态资源延时属性  文件大小：{file_size}KB  延时时间：{delay}s')
        time.sleep(delay)

    return send_from_directory(self.static_folder, file_name)


class MockRequestParseError(Exception):
  """mock 请求参数解析异常"""

  def __init__(self, message: str) -> None:
    self.message: str = message
    super().__init__(message)


def parse_flask_request(
    request: Request,
    path: str,
    get_params_json_string: Callable[[Union[Dict[str, Any], str]], str],
) -> ParsedRequest:
  """
  解析 Flask request 对象为 handler 所需的纯参数

  Returns:
    ParsedRequest(method, route, request_content_type, params_json)
  """
  method: str = request.method
  route: str = '/' + path
  if method == 'GET':
    route = remove_url_query(route)

  content_type_enum: RequestContentType = get_request_content_type(
    request.headers.get('content-type') or '', method
  )
  request_content_type: str = content_type_enum.value
  params: str = get_params_json_string({})

  if method == 'POST':
    if content_type_enum == RequestContentType.APPLICATION_X_WWW_FORM_URLENCODED:
      params = get_params_json_string(dict(request.form or {}))
    elif content_type_enum == RequestContentType.APPLICATION_JSON:
      params = get_params_json_string(request.get_data(as_text=True))
    elif content_type_enum == RequestContentType.MULTIPART_FORM_DATA:
      try:
        multipart_dict: Dict[str, Any] = dict(request.form or {})
        file = request.files.get('file')
        if file:
          content: bytes = remove_byte_empty_content(file.read())
          file_md5: str = f'file-{create_md5(content)}'
          multipart_dict['file'] = file_md5
          print('params 存在 file 传参：', multipart_dict)
        params = get_params_json_string(multipart_dict)
      except Exception as e:
        print('Mock Server 解析 multipart/form-data 传参异常', e)
        raise MockRequestParseError('multipart/form-data parse error')
    else:
      # 未识别的 content-type 按 NONE 处理，params 保持空对象
      params = get_params_json_string({})
  elif method == 'GET':
    params = get_params_json_string(dict(request.args or {}))

  return ParsedRequest(method, route, request_content_type, params)


class MockRequestHandler:
  """
  mock 接口请求处理器

  负责根据路由、方法、content-type 和 params 匹配对应的 mock 响应数据，
  并支持按单条 timeout 或全局延时模拟接口响应延迟。
  """

  def __init__(
      self,
      api_dict: MockApiDict,
      response_delay: int,
      get_request_key: Callable[[str, str, str], str],
      get_response_key: Callable[[str, str, str], str],
  ) -> None:
    self.api_dict: MockApiDict = api_dict
    self.response_delay: int = response_delay
    self.get_request_key: Callable[[str, str, str], str] = get_request_key
    self.get_response_key: Callable[[str, str, str], str] = get_response_key

  def handle(self, method: str, route: str, request_content_type: str, params: str) -> FlaskRouteResult:
    """匹配 mock 数据并返回响应"""
    request_key: str = self.get_request_key(route, method, request_content_type)
    if request_key not in self.api_dict:
      return jsonify({'error': 'Not Found'}), 404

    response_key: str = self.get_response_key(method, request_content_type, params)

    if response_key in self.api_dict[request_key]:
      entry: MockApiEntry = self.api_dict[request_key][response_key]
    else:
      # 没命中 mock 数据，直接返回最后一条数据
      print(f'mock 数据命中失败：\n - {method} {route} {params}')
      if not self.api_dict[request_key]:
        return jsonify({'error': 'No valid mock data'}), 404
      last_response_key: str = list(self.api_dict[request_key].keys())[-1]
      entry: MockApiEntry = self.api_dict[request_key][last_response_key]

    # 接口响应延时（单条 timeout 优先于全局 response_delay）
    per_entry_delay: int = entry.get('timeout', 0)
    if per_entry_delay > 0:
      print(f'接口响应延时（单条）：{per_entry_delay}ms, route：{route}')
      time.sleep(per_entry_delay / 1000)
    elif self.response_delay > 0:
      print(f'接口响应延时（全局）：{self.response_delay}ms, route：{route}')
      time.sleep(self.response_delay / 1000)

    return jsonify(entry['response'])
