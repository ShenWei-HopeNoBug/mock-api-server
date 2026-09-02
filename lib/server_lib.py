# -*- coding: utf-8 -*-
import json
import os
import re
import time
import threading
from collections import OrderedDict
from email.utils import formatdate, parsedate_to_datetime
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar, Union

import mimetypes
from flask import Request, send_from_directory, jsonify, Response

from config.enum.SERVER import STATIC_IMAGE_CACHE_MAX_AGE, STATIC_PARTIAL_CACHE_MAX_AGE
from config.route import STATIC_DELAY_ROUTE
from lib.db import MockDBCache
from lib.logger_lib import APP_LOGGER
from lib.download_lib import get_static_match_regexp
from lib.throttle_lib import ThrottleStrategy
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
  RequestHeaders,
  RequestKey,
  RequestKeyFunc,
  ResolveFileResult,
  ResponseKey,
  ResponseKeyFunc,
  ResponseMeta,
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
      static_load_speed: int,
      static_folder: str,
      max_delay: Union[int, float],
      throttle_strategy: Optional[ThrottleStrategy] = None,
  ) -> None:
    self.static_load_speed: int = static_load_speed
    self.static_folder: str = os.path.join(work_dir, static_folder)
    self.max_delay: Union[int, float] = max_delay
    self._throttle: Optional[ThrottleStrategy] = throttle_strategy

  def match(self, path: str, request_headers: RequestHeaders) -> FlaskRouteResult:
    """
    匹配并返回本地静态资源文件。

    编排职责：
    1. 解析并校验本地文件；
    2. 基于资源类型/限速开关/Range 头选择 direct 或 throttled；
    3. 将协议细节（304/206/416、缓存头拼装）下沉到子方法。
    """
    route_path: str = '/' + path
    resolved: ResolveFileResult = self._resolve_file(route_path)

    if not resolved.get('valid'):
      return resolved.get('result') or ('Not Found', 404)

    file_path: str = resolved.get('file_path')
    file_name: str = resolved.get('file_name')
    range_header: Optional[str] = request_headers.get('Range')

    # 是否走节流读取由独立决策方法统一判断，避免 match 中出现大量资源分支 if-else。
    if self._should_use_throttled(file_path, range_header):
      return self._serve_throttled(file_path, file_name, range_header, request_headers)

    # 其余场景统一走 direct：
    # - 无 Range 的常规静态资源请求
    # - 限速视频探测请求（200 empty，引导后续 Range）
    # - 不限速含 Range 的标准 send_from_directory 条件处理
    return self._serve_direct(file_path, file_name, request_headers)

  def _should_use_throttled(self, file_path: str, range_header: Optional[str]) -> bool:
    """
    判断当前请求是否应走节流读取。

    规则（保持现有行为）：
    - 未开启限速：全部 direct；
    - 图片：开启限速后无论是否带 Range 都节流（修复图片空 body 问题）；
    - 视频：仅带 Range 时节流（无 Range 先走 probe）；
    - 其他类型：仅带 Range 时节流。
    """
    if self.static_load_speed <= 0:
      return False
    if self._is_image(file_path):
      return True
    if self._is_video(file_path):
      return range_header is not None
    return range_header is not None

  def _serve_direct(
      self,
      file_path: str,
      file_name: str,
      request_headers: RequestHeaders,
  ) -> FlaskRouteResult:
    """直接返回文件（限速时仅视频返回探测头部；不限速含 Range 时启用条件处理）"""
    # 入口处 stat 一次，后续全部复用，避免 TOCTOU 竞态
    stat: os.stat_result = os.stat(file_path)

    # 浏览器缓存校验：条件请求命中时返回 304，跳过延时
    if self._check_cache_hit(file_path, request_headers, stat):
      print(f'静态资源缓存命中(304)  文件：{file_name}')
      return self._build_304_response(file_path, stat)

    # 有限速且为视频时，200 探测请求返回空 body + Content-Length: 0：
    # 浏览器收到 Accept-Ranges: bytes 后会立即改发 Range 请求走 _serve_throttled 节流路径，
    # 避免对 69MB 大文件做无节流的全量传输导致播放卡死。
    if self.static_load_speed > 0 and self._is_video(file_path):
      content_type: str = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
      headers: Dict[str, str] = {
        'Accept-Ranges': 'bytes',
        'Content-Type': content_type,
        'Content-Length': '0',
      }
      self._apply_common_headers(headers, file_path, stat, status_code=200)
      print(f'静态资源探测响应(200 empty)  文件：{file_name}  大小：{self._format_size(stat.st_size)}')
      return Response(b'', status=200, headers=headers)

    # 无限速场景下：
    # - 有 Range 头时启用 conditional，交给底层处理 206/416 等分段响应
    # - 无 Range 时保持 conditional=False，避免与自定义 _check_cache_hit 双 ETag 体系冲突
    has_range_header: bool = request_headers.get('Range') is not None
    result = send_from_directory(self.static_folder, file_name, conditional=has_range_header)
    # send_from_directory 返回 200/206/304 时均需补充自定义缓存头，
    # 确保后续条件请求的 ETag / Cache-Control 格式与 _build_304_response 一致
    if hasattr(result, 'headers') and result.status_code in (200, 206, 304):
      self._apply_cache_headers(result, file_path, stat)
    return result

  def _resolve_file(self, route_path: str) -> ResolveFileResult:
    """路径解析 + 安全校验"""
    # 非文件请求，跳过
    if not is_file_request(route_path):
      return {'file_path': '', 'file_name': '', 'valid': False, 'result': ('Not Found', 404)}

    # os.path.basename 跨平台识别 / 和 \，自动剥离所有目录层级，从源头杜绝 .. 穿越
    file_name: str = os.path.basename(route_path)
    if not file_name:
      return {'file_path': '', 'file_name': '', 'valid': False, 'result': ('Not Found', 404)}

    file_path: str = os.path.realpath(os.path.join(self.static_folder, file_name))
    # containment 校验：确保最终路径仍在 static_folder 目录下（realpath 解析符号链接）
    static_dir: str = os.path.realpath(self.static_folder)
    if not file_path.startswith(static_dir + os.sep):
      return {'file_path': '', 'file_name': '', 'valid': False, 'result': ('Forbidden', 403)}

    # 文件存在性校验：不存在时返回 404，避免后续 os.stat 抛出 FileNotFoundError
    if not os.path.isfile(file_path):
      return {'file_path': '', 'file_name': '', 'valid': False, 'result': ('Not Found', 404)}

    return {'file_path': file_path, 'file_name': file_name, 'valid': True, 'result': None}

  def _build_partial_meta(self, start: int, end: int, file_total: int) -> ResponseMeta:
    """有 Range：构建 206 Partial Content meta"""
    content_length: int = end - start + 1
    headers: Dict[str, str] = {
      'Content-Range': f'bytes {start}-{end}/{file_total}',
      'Accept-Ranges': 'bytes',
      'Vary': 'Range',
    }
    return ResponseMeta(status=206, headers=headers, start=start, end=end, content_length=content_length)

  def _build_full_meta(self, file_total: int) -> ResponseMeta:
    """无 Range：构建 200 OK meta"""
    headers: Dict[str, str] = {'Accept-Ranges': 'bytes'}
    return ResponseMeta(status=200, headers=headers, start=0, end=file_total - 1, content_length=file_total)

  def _serve_throttled(
      self,
      file_path: str,
      file_name: str,
      range_header: Optional[str],
      request_headers: RequestHeaders,
  ) -> FlaskRouteResult:
    """
    走节流读取：逐块读取 + per-chunk sleep。

    该方法只负责：
    - 打开文件并获取 file_total；
    - 通过 _build_throttled_meta_or_response 解析 Range/If-Range 并组装响应元信息；
    - 通过限速策略创建 reader 并返回最终 Response。
    """
    # 入口处 stat 一次，后续全部复用，避免 TOCTOU 竞态
    stat: os.stat_result = os.stat(file_path)

    # 浏览器缓存校验：条件请求命中时返回 304，跳过延时
    if self._check_cache_hit(file_path, request_headers, stat):
      print(f'静态资源缓存命中(304)  文件：{file_name}')
      return self._build_304_response(file_path, stat)

    # 先打开文件获取大小并解析 Range，随后关闭；实际读取由限速策略创建的 reader 重新打开
    try:
      f = open(file_path, 'rb')
    except (FileNotFoundError, OSError):
      return 'Not Found', 404

    with f:
      f.seek(0, 2)
      file_total: int = f.tell()

      content_type: str = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

      meta_or_response: Union[ResponseMeta, Response] = self._build_throttled_meta_or_response(
        file_path=file_path,
        file_name=file_name,
        range_header=range_header,
        request_headers=request_headers,
        stat=stat,
        file_total=file_total,
        content_type=content_type,
      )
      if isinstance(meta_or_response, Response):
        return meta_or_response
      meta: ResponseMeta = meta_or_response

    # 限速策略对象由外部注入，_serve_throttled 只负责协议处理 + 调用策略创建 reader
    reader = self._throttle.create_reader(file_path, meta.start, meta.content_length)

    print(
      f'静态资源节流  文件：{file_name}  大小：{self._format_size(meta.content_length)}  速率：{self._format_size(self.static_load_speed * 1024)}/s')
    return Response(reader, status=meta.status, headers=meta.headers)

  def _build_throttled_meta_or_response(
      self,
      file_path: str,
      file_name: str,
      range_header: Optional[str],
      request_headers: RequestHeaders,
      stat: os.stat_result,
      file_total: int,
      content_type: str,
  ) -> Union[ResponseMeta, Response]:
    """
    构建节流响应的元信息（ResponseMeta）或直接返回终态响应（如 416）。

    该方法集中处理 Range/If-Range 语义，避免 _serve_throttled 里散落协议分支。
    """
    # If-Range 校验：不匹配时忽略 Range，转为完整文件候选（200）
    effective_range_header: Optional[str] = range_header
    if not self._check_if_range(stat, request_headers):
      effective_range_header = None

    range_info: Optional[Tuple[int, int]] = self._parse_range(effective_range_header, file_total)

    # 有 Range 头但无法解析/不满足时，返回 416（RFC 7233）
    if effective_range_header is not None and range_info is None:
      print(f'静态资源非法 Range 416  文件：{file_name}  Range：{effective_range_header}')
      return self._build_416_response(content_type, file_total, stat)

    if range_info is not None:
      meta: ResponseMeta = self._build_partial_meta(range_info[0], range_info[1], file_total)
    else:
      meta = self._build_full_meta(file_total)

    # 视频在限速模式下必须避免 200 全量传输：
    # 若最终退化为 200，则返回 416 引导浏览器重发不带 If-Range 的 Range 请求。
    if meta.status == 200 and self._is_video(file_path):
      print(f'静态资源视频 416 回退  文件：{file_name}  大小：{self._format_size(file_total)}')
      return self._build_416_response(content_type, file_total, stat)

    meta.headers['Content-Length'] = str(meta.content_length)
    meta.headers['Content-Type'] = content_type
    self._apply_common_headers(meta.headers, file_path, stat, status_code=meta.status)
    return meta

  @staticmethod
  def _format_size(size_bytes: float) -> str:
    """将字节数动态格式化为 B/KB/MB 单位"""
    if size_bytes < 1024:
      return f'{size_bytes:.0f}B'
    if size_bytes < 1024 * 1024:
      return f'{size_bytes / 1024:.2f}KB'
    return f'{size_bytes / (1024 * 1024):.2f}MB'

  @staticmethod
  def _compute_etag(file_size: int, mtime: float) -> str:
    """基于文件大小 + mtime 生成强 ETag，避免读取文件内容算 hash 的 I/O 开销"""
    # 强 ETag（无 W/ 前缀）：If-Range 校验要求强 ETag，弱 ETag 会导致 Range 被忽略回退 200
    # 保留毫秒精度，避免同秒内文件修改（大小不变）产生相同 ETag
    return f'"{file_size}-{int(mtime * 1000)}"'

  def _check_if_range(self, stat: os.stat_result, request_headers: RequestHeaders) -> bool:
    """
    校验 If-Range 头是否匹配当前资源。

    - If-Range 为 ETag：与文件 ETag 精确比较（RFC 7233 §3.2 要求强比较）
    - If-Range 为 HTTP-date：与文件 mtime 比较，精确匹配则命中

    无 If-Range 头时返回 True（无约束，正常走 Range 路径）。
    """
    if_range: Optional[str] = request_headers.get('If-Range')
    if not if_range:
      return True

    # 尝试作为 ETag 比较（RFC 7233 §3.2 要求强比较，弱 ETag 不可用于 If-Range）
    if if_range.startswith('W/'):
      return False
    etag: str = self._compute_etag(stat.st_size, stat.st_mtime)
    if if_range == etag:
      return True

    # 尝试作为 HTTP-date 比较
    try:
      ir_dt = parsedate_to_datetime(if_range)
      if ir_dt is not None:
        mtime_dt = parsedate_to_datetime(self._format_http_date(stat.st_mtime))
        if mtime_dt is not None and ir_dt == mtime_dt:
          return True
    except (TypeError, ValueError):
      pass

    return False

  @staticmethod
  def _format_http_date(timestamp: float) -> str:
    """将时间戳转为 HTTP 标准日期格式（RFC 7231 IMF-fixdate）"""
    return formatdate(timestamp, usegmt=True)

  @staticmethod
  def _is_image(file_path: str) -> bool:
    """判断文件 MIME 类型是否为图片"""
    mime_type: Optional[str] = mimetypes.guess_type(file_path)[0]
    return mime_type is not None and mime_type.startswith('image/')

  @staticmethod
  def _is_video(file_path: str) -> bool:
    """判断文件 MIME 类型是否为视频"""
    mime_type: Optional[str] = mimetypes.guess_type(file_path)[0]
    return mime_type is not None and mime_type.startswith('video/')

  def _build_cache_control(self, file_path: str) -> str:
    """根据文件类型生成 Cache-Control 值：图片走强缓存，其他走协商缓存"""
    if self._is_image(file_path):
      return f'public, max-age={STATIC_IMAGE_CACHE_MAX_AGE}'
    return 'public, max-age=0, must-revalidate'

  @staticmethod
  def _build_partial_cache_control() -> str:
    """206 Partial Content 专用 Cache-Control：所有文件类型统一强缓存"""
    return f'public, max-age={STATIC_PARTIAL_CACHE_MAX_AGE}'

  def _check_cache_hit(
      self,
      file_path: str,
      request_headers: RequestHeaders,
      stat: os.stat_result,
  ) -> bool:
    """
    判断浏览器条件请求是否命中缓存。

    遵循 RFC 7232 §6 优先级：
    1. If-None-Match 存在时，仅做 ETag 校验，忽略 If-Modified-Since
    2. If-None-Match 不存在时，才检查 If-Modified-Since

    - If-None-Match：* 匹配任意存在资源；否则与文件 ETag 逐个比较（支持弱 ETag W/ 前缀）
    - If-Modified-Since：与文件 mtime 比较，请求时间 >= mtime 则命中

    stat 由调用方在入口处统一获取并传入，避免 TOCTOU 竞态。
    """
    file_size: int = stat.st_size
    mtime: float = stat.st_mtime

    # If-None-Match 校验（存在时忽略 If-Modified-Since）
    if_none_match: Optional[str] = request_headers.get('If-None-Match')
    if if_none_match:
      # If-None-Match: * 匹配任意存在资源
      if if_none_match.strip() == '*':
        return True
      etag: str = self._compute_etag(file_size, mtime)
      # 弱比较归一化：去掉可选 W/ 前缀后再比较（RFC 7232）
      normalized_etag: str = etag[2:].strip() if etag.startswith('W/') else etag.strip()
      # 浏览器可能发送多个 ETag，逗号分隔
      for client_etag in if_none_match.split(','):
        client_etag = client_etag.strip()
        normalized_client_etag: str = client_etag[2:].strip() if client_etag.startswith('W/') else client_etag
        # 弱 ETag 比较：W/"..." 与 "..." 视为等价
        if normalized_client_etag == normalized_etag:
          return True
      # If-None-Match 存在但未命中，按 RFC 忽略 If-Modified-Since，直接返回未命中
      return False

    # If-Modified-Since 校验（仅在 If-None-Match 不存在时执行）
    if_modified_since: Optional[str] = request_headers.get('If-Modified-Since')
    if if_modified_since:
      try:
        ims_dt = parsedate_to_datetime(if_modified_since)
        if ims_dt is not None:
          mtime_dt = parsedate_to_datetime(self._format_http_date(mtime))
          if mtime_dt is not None and ims_dt >= mtime_dt:
            return True
      except (TypeError, ValueError):
        pass

    return False

  def _apply_cache_headers(
      self,
      response: Response,
      file_path: str,
      stat: os.stat_result,
  ) -> None:
    """为 send_from_directory 返回的 Response 对象补充缓存头"""
    self._apply_common_headers(response.headers, file_path, stat, status_code=response.status_code)

  def _apply_common_headers(
      self,
      headers: Dict[str, str],
      file_path: str,
      stat: os.stat_result,
      status_code: int,
  ) -> None:
    """
    统一补充校验器与缓存控制头。

    - ETag / Last-Modified：用于协商缓存、If-Range/If-None-Match 校验；
    - Cache-Control：206/416 走 partial 强缓存，其余沿用类型化缓存策略。
    """
    headers['ETag'] = self._compute_etag(stat.st_size, stat.st_mtime)
    headers['Last-Modified'] = self._format_http_date(stat.st_mtime)
    if status_code in (206, 416):
      headers['Cache-Control'] = self._build_partial_cache_control()
    else:
      headers['Cache-Control'] = self._build_cache_control(file_path)

  def _build_304_response(self, file_path: str, stat: os.stat_result) -> FlaskRouteResult:
    """构建 304 Not Modified 响应（无 body、无延时、附带缓存头）"""
    headers: Dict[str, str] = {}
    self._apply_common_headers(headers, file_path, stat, status_code=304)
    return Response('', status=304, headers=headers)

  def _build_416_response(self, content_type: str, file_total: int, stat: os.stat_result) -> Response:
    """构建 416 Range Not Satisfiable 响应"""
    headers_416: Dict[str, str] = {
      'Content-Range': f'bytes */{file_total}',
      'Accept-Ranges': 'bytes',
      'Content-Type': content_type,
      'Content-Length': '0',
    }
    self._apply_common_headers(headers_416, file_path='', stat=stat, status_code=416)
    return Response(b'', status=416, headers=headers_416)

  @staticmethod
  def _parse_range(range_header: Optional[str], file_total: int) -> Optional[Tuple[int, int]]:
    """
    解析 Range 头，返回 (start, end) 闭区间字节偏移。

    支持格式：
      - bytes=start-end  → 返回 [start, min(end, file_total-1)]
      - bytes=start-     → 从 start 到文件末尾
      - bytes=-suffix    → 取文件最后 suffix 个字节

    返回 None 的情况（表示完整文件，由调用方走 200 路径）：
      - 无 Range 头
      - file_total <= 0（空文件，避免 end = -1 产生非法 Content-Range）
      - 格式不匹配
      - start >= file_total（起始越界）
      - start > end（经 min 截断后区间为空）
      - suffix <= 0
      - bytes=-（start 和 end 均为空，非有效 Range）
    """
    # 前置拦截：无 Range 头或空文件，直接走完整文件路径
    if not range_header or file_total <= 0:
      return None
    match = re.match(r'bytes=(\d*)-(\d*)$', range_header.strip())
    if not match:
      return None
    start_str, end_str = match[1], match[2]

    # 情况 1：bytes=start-end，指定区间
    # end 超出文件大小时截断为 file_total-1；截断后 start > end 说明区间为空
    if start_str and end_str:
      start, end = int(start_str), int(end_str)
      if start >= file_total:
        return None
      end = min(end, file_total - 1)
      if start > end:
        return None
      return (start, end)

    # 情况 2：bytes=start-，从 start 到文件末尾
    if start_str and not end_str:
      start = int(start_str)
      if start >= file_total:
        return None
      return (start, file_total - 1)

    # 情况 3：bytes=-suffix，取文件最后 suffix 个字节
    # suffix 超过文件大小时从 0 开始；suffix <= 0 无意义
    if not start_str and end_str:
      suffix = int(end_str)
      if suffix <= 0:
        return None
      start = max(file_total - suffix, 0)
      return (start, file_total - 1)

    # 情况 4：bytes=-（start 和 end 均为空），非有效 Range
    return None


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
