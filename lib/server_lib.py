# -*- coding: utf-8 -*-
import json
import os
import re
import time
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from flask import Request, send_from_directory, jsonify

from config.route import STATIC_DELAY_ROUTE
from lib.db import MockDBCache
from lib.download_lib import get_static_match_regexp
from lib.utils_lib import (
  create_md5,
  get_request_content_type,
  is_file_request,
  remove_byte_empty_content,
  remove_url_query,
)
from app_types.app_gui_types import RequestContentType
from app_types.global_types import JsonValue
from app_types.mock_server_types import (
  ApiMatchMeta,
  ClientStateResult,
  DeviceId,
  DeviceState,
  FlaskRouteResult,
  HttpMethod,
  MockApiEntry,
  MockApiMap,
  ParamsJson,
  ParamsJsonStringFunc,
  ParsedRequest,
  RequestContentTypeStr,
  RequestKey,
  RequestKeyFunc,
  ResponseKey,
  ResponseKeyFunc,
  Route,
  VariantMeta,
  VariantState,
)

T = TypeVar('T')


class ThreadSafeLRUCache(Generic[T]):
  """
  线程安全的 LRU 缓存

  基于 OrderedDict 实现最近最久未使用淘汰，配合 Lock 保证多线程安全。
  调用点直接使用该通用泛型类，无需额外封装。
  """

  def __init__(self, limit: int):
    self._limit: int = limit
    self._cache: 'OrderedDict[str, T]' = OrderedDict()
    self._lock: threading.Lock = threading.Lock()

  def get(self, key: str) -> Optional[T]:
    """读取缓存，命中时移到队尾表示最近使用"""
    with self._lock:
      if key not in self._cache:
        return None
      self._cache.move_to_end(key)
      return self._cache[key]

  def set(self, key: str, value: T) -> None:
    """写入缓存，超过上限时淘汰最久未使用"""
    with self._lock:
      self._cache[key] = value
      self._cache.move_to_end(key)
      if len(self._cache) > self._limit:
        self._cache.popitem(last=False)

  def set_once(self, key: str, value: T) -> bool:
    """
    原子性 check-then-set：
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


# 静态资源 URL 替换函数类型
AssetsReplaceFunc = Callable[[str], str]


def create_assets_replace_func(
    include_files: List[str],
    static_host: str,
    static_url_path: str,
    static_load_speed: int,
) -> Optional[AssetsReplaceFunc]:
  """
  根据 include_files 等配置构造静态资源 URL 替换函数。

  返回的函数接收原始 response 文本，返回替换后的文本；
  若 include_files 为空，返回 None，表示无需替换。
  """
  if not include_files:
    return None

  assets_reg: re.Pattern = get_static_match_regexp(include_files)
  assets_route: str = STATIC_DELAY_ROUTE if static_load_speed > 0 else static_url_path
  assets_base_url: str = f'{static_host}{assets_route}'

  def replace_assets(response_text: str) -> str:
    def repl(match: re.Match) -> str:
      assets_url: str = match[0]
      file_name: str = assets_url.split('/')[-1]
      return f'{assets_base_url}/{file_name}'

    return assets_reg.sub(repl, response_text)

  return replace_assets


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
      cache: ThreadSafeLRUCache[bool],
      max_delay: Union[int, float],
  ) -> None:
    self.work_dir: str = work_dir
    self.static_url_path: str = static_url_path
    self.static_load_speed: int = static_load_speed
    self.static_folder: str = static_folder
    self.cache: ThreadSafeLRUCache[bool] = cache
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
      is_first: bool = self.cache.set_once(search_key, True)
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


class ClientStateManager:
  """
  基于 Mock-Server-Device-Id Header 的客户端状态管理器

  - 不生成 id，只接受客户端传入的 device_id
  - 内部用 create_md5 对 device_id 归一化，避免超长或特殊字符 key
  - 使用 OrderedDict + Lock 做 LRU，线程安全
  """

  def __init__(self, limit: int = 1000) -> None:
    self._limit: int = limit
    self._store: 'OrderedDict[str, DeviceState]' = OrderedDict()
    self._lock: threading.Lock = threading.Lock()

  def get_or_create(self, device_id: DeviceId) -> ClientStateResult:
    key: str = create_md5(device_id[:128])

    with self._lock:
      if key in self._store:
        self._store.move_to_end(key)
        return {
          'device_id': device_id,
          'state': self._store[key],
          'is_new': False,
        }

      self._store[key] = {}
      if len(self._store) > self._limit:
        self._store.popitem(last=False)

      return {
        'device_id': device_id,
        'state': self._store[key],
        'is_new': True,
      }

  def get(self, device_id: DeviceId) -> Optional[DeviceState]:
    key: str = create_md5(device_id[:128])
    with self._lock:
      return self._store.get(key)

  def set(self, device_id: DeviceId, state: DeviceState) -> None:
    key: str = create_md5(device_id[:128])
    with self._lock:
      self._store[key] = state
      self._store.move_to_end(key)

  def delete(self, device_id: DeviceId) -> None:
    key: str = create_md5(device_id[:128])
    with self._lock:
      self._store.pop(key, None)


def parse_flask_request(
    request: Request,
    path: str,
    get_params_json_string: ParamsJsonStringFunc,
) -> ParsedRequest:
  """
  解析 Flask request 对象为 handler 所需的纯参数

  Returns:
    ParsedRequest(method, route, request_content_type, params_json)
  """
  method: HttpMethod = request.method
  route: Route = '/' + path
  if method == 'GET':
    route = remove_url_query(route)

  content_type_enum: RequestContentType = get_request_content_type(
    request.headers.get('content-type') or '', method
  )
  request_content_type: RequestContentTypeStr = content_type_enum.value
  params: ParamsJson = get_params_json_string({})

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

  负责根据路由、方法、content-type 和 params 命中轻量匹配映射，
  并根据 device 状态按顺序命中 response 变体；
  响应体按需从 DB 加载并缓存，支持按单条 timeout 或全局延时模拟接口响应延迟。
  """

  def __init__(
      self,
      mock_api_map: MockApiMap,
      work_dir: str,
      response_cache: 'ThreadSafeLRUCache[MockApiEntry]',
      response_delay: int,
      get_request_key: RequestKeyFunc,
      get_response_key: ResponseKeyFunc,
      replace_assets: Optional[AssetsReplaceFunc] = None,
  ) -> None:
    self.mock_api_map: MockApiMap = mock_api_map
    self.work_dir: str = work_dir
    self.response_cache: 'ThreadSafeLRUCache[MockApiEntry]' = response_cache
    self.response_delay: int = response_delay
    self.get_request_key: RequestKeyFunc = get_request_key
    self.get_response_key: ResponseKeyFunc = get_response_key

    # 静态资源替换由外部构造并传入，MockRequestHandler 不依赖 include_files 等配置
    self.replace_assets: Optional[AssetsReplaceFunc] = replace_assets

    # 变体状态锁：每个 device 一把锁，保证同一设备并发请求时状态不竞争
    self._state_locks: Dict[str, threading.Lock] = {}
    self._state_locks_lock: threading.Lock = threading.Lock()

  def _get_state_lock(self, device_id: DeviceId) -> threading.Lock:
    """获取/创建某个 device 的状态锁，保证变体状态并发安全"""
    key: str = create_md5(device_id[:128])
    with self._state_locks_lock:
      if key not in self._state_locks:
        self._state_locks[key] = threading.Lock()
      return self._state_locks[key]

  def _select_variant(
      self,
      device_state: DeviceState,
      api_data_id: str,
      variants: List[VariantMeta],
  ) -> str:
    """
    在已加锁的 device_state 上，按 timeout 规则选择本次应命中的变体 id。

    - 首次命中取 variants[0]， next_index 更新为 1；
    - 之后按顺序推进，命中最后一个后停留在最后一个；
    - 超过 last_variant_timeout 未请求，重置为 variants[0]。
    """
    variant_states: Dict[str, Any] = device_state.setdefault('variant_state', {})

    state: VariantState = variant_states.setdefault(
      api_data_id,
      {
        'next_index': 0,
        'last_hit_time': 0.0,
        'last_variant_timeout': 0,
      },
    )

    now: float = time.time()
    n: int = len(variants)

    # timeout 回退：上次命中变体的 idle 超时时间内没有新请求，重置为第一个
    if state['last_variant_timeout'] > 0:
      idle_ms: float = (now - state['last_hit_time']) * 1000
      if idle_ms > state['last_variant_timeout']:
        state['next_index'] = 0

    selected_index: int = min(state['next_index'], n - 1)
    selected: VariantMeta = variants[selected_index]

    # 更新状态：记录本次命中时间和该变体的 timeout，推进索引
    state['last_hit_time'] = now
    state['last_variant_timeout'] = selected['timeout']
    state['next_index'] = min(selected_index + 1, n - 1)

    return selected['id']

  def _load_main_response(self, api_data_id: str) -> MockApiEntry:
    """加载主响应（api_data.response），经静态资源替换后缓存"""
    cache_key: str = f'api:{api_data_id}'
    entry: Optional[MockApiEntry] = self.response_cache.get(cache_key)
    if entry is not None:
      return entry

    mock_db = MockDBCache.get(self.work_dir)
    api_data = mock_db.get_api_detail(api_data_id)
    if not api_data:
      return {'response': {}, 'timeout': 0}

    response_text: str = api_data.get('response', '{}')
    if self.replace_assets:
      response_text = self.replace_assets(response_text)
    try:
      response: JsonValue = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
      response = {}

    # 缓存中 timeout 仅作占位，真实响应延时以 ApiMatchMeta.timeout 为准
    entry: MockApiEntry = {'response': response, 'timeout': 0}
    self.response_cache.set(cache_key, entry)
    return entry

  def _load_variant_response(self, variant_id: str) -> MockApiEntry:
    """加载变体响应，经静态资源替换后缓存"""
    cache_key: str = f'variant:{variant_id}'
    entry: Optional[MockApiEntry] = self.response_cache.get(cache_key)
    if entry is not None:
      return entry

    mock_db = MockDBCache.get(self.work_dir)
    variant = mock_db.get_variant_by_id(variant_id)
    if not variant:
      return {'response': {}, 'timeout': 0}

    response_text: str = variant.get('response', '{}')
    if self.replace_assets:
      response_text = self.replace_assets(response_text)
    try:
      response: JsonValue = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
      response = {}

    entry: MockApiEntry = {'response': response, 'timeout': 0}
    self.response_cache.set(cache_key, entry)
    return entry

  def _get_api_match_meta(
      self,
      request_key: RequestKey,
      response_key: ResponseKey,
  ) -> Optional[ApiMatchMeta]:
    """根据 request_key / response_key 命中 ApiMatchMeta，未命中时 fallback 默认"""
    if request_key not in self.mock_api_map:
      return None

    inner: Dict[ResponseKey, ApiMatchMeta] = self.mock_api_map[request_key]

    if response_key in inner:
      return inner[response_key]

    # 未命中 response_key，fallback 到该 request 最后插入的匹配项
    # Python 3.7+ dict 保持插入顺序，next(reversed(inner)) 取最后 key，无需 list 分配
    if not inner:
      return None

    try:
      default_key: ResponseKey = next(reversed(inner))
    except StopIteration:
      return None

    return inner[default_key]

  def handle(
      self,
      method: HttpMethod,
      route: Route,
      request_content_type: RequestContentTypeStr,
      params: ParamsJson,
      state_result: Optional[ClientStateResult] = None,
  ) -> FlaskRouteResult:
    """匹配 mock 数据并返回响应"""
    request_key: RequestKey = self.get_request_key(route, method, request_content_type)
    response_key: ResponseKey = self.get_response_key(method, request_content_type, params)
    meta: Optional[ApiMatchMeta] = self._get_api_match_meta(request_key, response_key)

    if meta is None:
      print(f'mock 数据命中失败：\n - {method} {route} {params}')
      return jsonify({'error': 'No valid mock data'}), 404

    entry: MockApiEntry

    # 变体命中：有启用变体且存在 device 状态时按顺序命中
    if meta['variants'] and state_result is not None:
      device_id: DeviceId = state_result['device_id']
      with self._get_state_lock(device_id):
        variant_id: str = self._select_variant(
          state_result['state'],
          meta['api_data_id'],
          meta['variants'],
        )
      entry = self._load_variant_response(variant_id)
    else:
      # 无启用变体 或 无 device_id：使用 api_data.response 兜底
      entry = self._load_main_response(meta['api_data_id'])

    # 接口响应延时（单条 timeout 优先于全局 response_delay）
    per_entry_delay: int = meta['timeout']
    if per_entry_delay > 0:
      print(f'接口响应延时（单条）：{per_entry_delay}ms, route：{route}')
      time.sleep(per_entry_delay / 1000)
    elif self.response_delay > 0:
      print(f'接口响应延时（全局）：{self.response_delay}ms, route：{route}')
      time.sleep(self.response_delay / 1000)

    return jsonify(entry['response'])


# mock 服务进程启动（子进程入口，避免在 qt_win/app.py 中定义以减少子进程模块导入开销）
def server_process_start(server_config: Dict[str, Any]) -> None:
  print('server_config', server_config)
  port = server_config.get('port', 5000)
  work_dir = server_config.get('work_dir', '.')
  response_delay = server_config.get('response_delay', 0)
  static_load_speed = server_config.get('static_load_speed', 0)
  # 延迟导入避免与 module.mock_server 形成循环依赖
  from module.mock_server import MockServer
  # 初始化 mock 服务实例
  server = MockServer(
    work_dir=work_dir,
    port=port,
    response_delay=response_delay,
    static_load_speed=static_load_speed,
  )
  # 启动本地 mock 服务
  server.start_server()
