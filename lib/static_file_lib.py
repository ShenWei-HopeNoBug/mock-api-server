# -*- coding: utf-8 -*-
"""
静态资源请求处理模块

包含静态资源 URL 替换函数构造、静态文件请求处理器（匹配/缓存/Range/限速）。
从 lib/server_lib.py 中抽离，降低 server_lib.py 的模块体积。
"""
import os
import re
import mimetypes
from email.utils import formatdate, parsedate_to_datetime
from typing import Dict, List, Optional, Tuple, Union

from flask import Response, send_from_directory

from config.enum.SERVER import STATIC_IMAGE_CACHE_MAX_AGE, STATIC_PARTIAL_CACHE_MAX_AGE
from config.route import STATIC_DELAY_ROUTE
from lib.download_lib import get_static_match_regexp
from lib.utils_lib import is_file_request
from app_types.mock_server_types import (
  AssetsReplaceFunc,
  FlaskRouteResult,
  RequestHeaders,
  ResolveFileResult,
  ResponseMeta,
  ThrottleStrategy,
)


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

  @staticmethod
  def _resolve_file_fail(msg: str, status_code: int) -> ResolveFileResult:
    """构造路径解析失败结果，统一 valid=False 时的字段填充"""
    return {'file_path': '', 'file_name': '', 'valid': False, 'result': (msg, status_code)}

  def _resolve_file(self, route_path: str) -> ResolveFileResult:
    """路径解析 + 安全校验"""
    # 非文件请求，跳过
    if not is_file_request(route_path):
      return self._resolve_file_fail('Not Found', 404)

    # os.path.basename 跨平台识别 / 和 \，自动剥离所有目录层级，从源头杜绝 .. 穿越
    file_name: str = os.path.basename(route_path)
    if not file_name:
      return self._resolve_file_fail('Not Found', 404)

    file_path: str = os.path.realpath(os.path.join(self.static_folder, file_name))
    # containment 校验：确保最终路径仍在 static_folder 目录下（realpath 解析符号链接）
    static_dir: str = os.path.realpath(self.static_folder)
    if not file_path.startswith(static_dir + os.sep):
      return self._resolve_file_fail('Forbidden', 403)

    # 文件存在性校验：不存在时返回 404，避免后续 os.stat 抛出 FileNotFoundError
    if not os.path.isfile(file_path):
      return self._resolve_file_fail('Not Found', 404)

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
    # create_reader 内部会重新 open 文件，可能因文件被删除/权限变更而抛异常，
    # 与上方第一次 open 的错误处理保持一致，返回 404 而非 500
    try:
      reader = self._throttle.create_reader(file_path, meta.start, meta.content_length)
    except (FileNotFoundError, OSError):
      return 'Not Found', 404

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
