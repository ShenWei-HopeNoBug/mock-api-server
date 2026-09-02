# -*- coding: utf-8 -*-
"""
静态资源限速策略模块

提供统一的 ThrottleStrategy 接口，支持多种限速方案替换测试：
- chunk_sleep：当前方案，固定 chunk + per-chunk sleep（脉冲式）
- small_chunk：小 chunk 高频脉冲，降低播放器感知停顿
- token_bucket：令牌桶，允许短暂突发但长期匀速（后续实现）

通过 create_throttle() 工厂函数按策略名创建，StaticFileHandler 只依赖接口，
切换策略时无需修改 StaticFileHandler 或 _serve_throttled。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Union

# 限速策略名 → ThrottleStrategy 子类
_STRATEGY_REGISTRY: Dict[str, type] = {}


def register_strategy(name: str):
  """策略注册装饰器"""
  def _wrap(cls: type) -> type:
    _STRATEGY_REGISTRY[name] = cls
    return cls
  return _wrap


class ThrottleStrategy(ABC):
  """限速策略统一接口"""

  @abstractmethod
  def create_reader(
      self,
      file_path: str,
      start: int,
      length: int,
  ) -> Any:
    """
    返回一个 file-like object（有 read() 方法）或 iterable[bytes]。
    WSGI server 通过 wsgi.file_wrapper 识别其 read() 方法，
    配合 Content-Length 头实现非 chunked 流式传输。
    """
    ...


class _ChunkSleepReader:
  """
  带节流的 file-like object，read() 时 per-chunk sleep 模拟弱网。

  WSGI server 通过 wsgi.file_wrapper 识别其 read() 方法，
  配合 Content-Length 头实现非 chunked 流式传输：
  - 浏览器边收边播（弱网模拟一卡一卡效果）
  - 非 chunked encoding，Chrome 可 disk cache 206
  """

  def __init__(
      self,
      file_path: str,
      start: int,
      length: int,
      chunk_size: int,
      per_chunk_delay: float,
  ) -> None:
    self._f = open(file_path, 'rb')
    self._f.seek(start)
    self._remaining: int = length
    self._chunk_size: int = chunk_size
    self._per_chunk_delay: float = per_chunk_delay

  def read(self, size: int = -1) -> bytes:
    if self._remaining <= 0:
      return b''
    read_size: int = min(size if size > 0 else self._chunk_size, self._remaining, self._chunk_size)
    data: bytes = self._f.read(read_size)
    if not data:
      self._remaining = 0
      return b''
    self._remaining -= len(data)
    if self._per_chunk_delay > 0:
      import time
      time.sleep(self._per_chunk_delay)
    return data

  def close(self) -> None:
    self._f.close()

  def __iter__(self):
    return self

  def __next__(self) -> bytes:
    data: bytes = self.read(self._chunk_size)
    if not data:
      raise StopIteration
    return data


@register_strategy('chunk_sleep')
class ChunkSleepThrottle(ThrottleStrategy):
  """
  固定 chunk + per-chunk sleep 脉冲式限速。

  每块读取 chunk_size 字节后 sleep per_chunk_delay 秒，
  播放器感知为"突发-停顿"脉冲式数据流。
  """

  def __init__(
      self,
      speed_kbps: int,
      max_delay: float,
      chunk_size: int = 64 * 1024,
  ) -> None:
    self._speed: int = speed_kbps
    self._max_delay: float = max_delay
    self._chunk_size: int = chunk_size

  def create_reader(self, file_path: str, start: int, length: int) -> _ChunkSleepReader:
    chunk_kb: float = self._chunk_size / 1024
    per_chunk_delay: float = min(chunk_kb / self._speed, self._max_delay)
    return _ChunkSleepReader(file_path, start, length, self._chunk_size, per_chunk_delay)


@register_strategy('small_chunk')
class SmallChunkThrottle(ThrottleStrategy):
  """
  小 chunk 高频脉冲限速。

  与 ChunkSleepThrottle 相同的算法，但使用更小的 chunk_size（默认 8KB），
  脉冲频率提高 8 倍，停顿间隔缩短到播放器难以感知的程度，
  在不改变算法的前提下显著减少播放器缓冲区低水位触发的额外请求。
  """

  def __init__(
      self,
      speed_kbps: int,
      max_delay: float,
      chunk_size: int = 8 * 1024,
  ) -> None:
    self._speed: int = speed_kbps
    self._max_delay: float = max_delay
    self._chunk_size: int = chunk_size

  def create_reader(self, file_path: str, start: int, length: int) -> _ChunkSleepReader:
    chunk_kb: float = self._chunk_size / 1024
    per_chunk_delay: float = min(chunk_kb / self._speed, self._max_delay)
    return _ChunkSleepReader(file_path, start, length, self._chunk_size, per_chunk_delay)


def create_throttle(
    strategy: str,
    speed_kbps: int,
    max_delay: float,
    **kwargs: Any,
) -> ThrottleStrategy:
  """
  工厂函数：按策略名创建限速策略实例。

  参数：
    strategy: 策略名（'chunk_sleep' / 'small_chunk' / ...）
    speed_kbps: 限速速率（KB/s）
    max_delay: 单次延时上限（秒）
    **kwargs: 策略特定参数（如 chunk_size）

  返回：
    ThrottleStrategy 实例
  """
  cls = _STRATEGY_REGISTRY.get(strategy)
  if cls is None:
    raise ValueError(
      f'未知的限速策略：{strategy}，可用策略：{list(_STRATEGY_REGISTRY.keys())}'
    )
  return cls(speed_kbps=speed_kbps, max_delay=max_delay, **kwargs)
