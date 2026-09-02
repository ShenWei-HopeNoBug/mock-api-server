# -*- coding: utf-8 -*-
"""
静态资源限速策略模块

提供统一的 ThrottleStrategy 接口，支持多种限速方案替换测试：
- chunk_sleep：固定 chunk + per-chunk sleep（脉冲式）
- small_chunk：小 chunk 高频脉冲，降低播放器感知停顿
- token_bucket：令牌桶，允许短暂突发但长期匀速
- leaky_bucket：漏桶，严格匀速输出，不允许突发

通过 create_throttle() 工厂函数按策略名创建，StaticFileHandler 只依赖接口，
切换策略时无需修改 StaticFileHandler 或 _serve_throttled。
"""
import time
from typing import Any, Dict, Optional

from app_types.mock_server_types import ThrottleStrategy
from lib.logger_lib import APP_LOGGER

# 限速策略名 → ThrottleStrategy 子类
_STRATEGY_REGISTRY: Dict[str, type] = {}


def register_strategy(name: str):
  """策略注册装饰器"""

  def _wrap(cls: type) -> type:
    _STRATEGY_REGISTRY[name] = cls
    return cls

  return _wrap


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


class _TokenBucketReader:
  """
  令牌桶 file-like object，允许短暂突发但长期匀速。

  桶容量为 burst_bytes，以 rate_bytes_per_sec 速率补充令牌。
  初始满桶，首屏可突发读取；之后按速率匀速补充。
  令牌不足时 sleep 等待，单次等待不超过 max_delay。
  """

  def __init__(
      self,
      file_path: str,
      start: int,
      length: int,
      chunk_size: int,
      rate_bytes_per_sec: float,
      burst_bytes: int,
      max_delay: float,
  ) -> None:
    self._f = open(file_path, 'rb')
    self._f.seek(start)
    self._remaining: int = length
    self._chunk_size: int = chunk_size
    self._rate: float = rate_bytes_per_sec
    self._burst: int = burst_bytes
    self._max_delay: float = max_delay
    self._tokens: float = float(burst_bytes)
    self._last_refill: float = time.monotonic()

  def _refill(self) -> None:
    now = time.monotonic()
    elapsed = now - self._last_refill
    self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
    self._last_refill = now

  def read(self, size: int = -1) -> bytes:
    if self._remaining <= 0:
      return b''
    read_size: int = min(size if size > 0 else self._chunk_size, self._remaining, self._chunk_size)

    self._refill()
    if self._tokens < read_size:
      deficit = read_size - self._tokens
      wait = min(deficit / self._rate, self._max_delay)
      time.sleep(wait)
      self._refill()

    data: bytes = self._f.read(read_size)
    if not data:
      self._remaining = 0
      return b''
    self._remaining -= len(data)
    self._tokens -= len(data)
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


class _LeakyBucketReader:
  """
  漏桶 file-like object，严格匀速输出，不允许突发。

  以 rate_bytes_per_sec 恒定速率输出数据。
  每次 read() 前根据已传输字节数计算理论时间戳，不足则等待。
  单次等待不超过 max_delay。
  """

  def __init__(
      self,
      file_path: str,
      start: int,
      length: int,
      chunk_size: int,
      rate_bytes_per_sec: float,
      max_delay: float,
  ) -> None:
    self._f = open(file_path, 'rb')
    self._f.seek(start)
    self._remaining: int = length
    self._chunk_size: int = chunk_size
    self._rate: float = rate_bytes_per_sec
    self._max_delay: float = max_delay
    self._start_time: float = time.monotonic()
    self._bytes_sent: int = 0

  def read(self, size: int = -1) -> bytes:
    if self._remaining <= 0:
      return b''
    read_size: int = min(size if size > 0 else self._chunk_size, self._remaining, self._chunk_size)

    # 传输 read_size 字节应有的最小耗时
    expected_elapsed = (self._bytes_sent + read_size) / self._rate
    actual_elapsed = time.monotonic() - self._start_time
    if actual_elapsed < expected_elapsed:
      wait = min(expected_elapsed - actual_elapsed, self._max_delay)
      time.sleep(wait)

    data: bytes = self._f.read(read_size)
    if not data:
      self._remaining = 0
      return b''
    self._remaining -= len(data)
    self._bytes_sent += len(data)
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


@register_strategy('token_bucket')
class TokenBucketThrottle(ThrottleStrategy):
  """
  令牌桶限速：允许短暂突发，长期匀速。

  桶初始满载，首屏可快速获取一批数据（突发），
  之后按 speed_kbps 速率匀速补充令牌。
  burst_seconds 控制桶容量（默认 1 秒数据量）。
  """

  def __init__(
      self,
      speed_kbps: int,
      max_delay: float,
      chunk_size: int = 64 * 1024,
      burst_seconds: float = 1.0,
  ) -> None:
    self._speed: int = speed_kbps
    self._max_delay: float = max_delay
    self._chunk_size: int = chunk_size
    self._rate: float = speed_kbps * 1024.0
    self._burst: int = int(self._rate * burst_seconds)

  def create_reader(self, file_path: str, start: int, length: int) -> _TokenBucketReader:
    return _TokenBucketReader(
      file_path, start, length,
      self._chunk_size, self._rate, self._burst, self._max_delay,
    )


@register_strategy('leaky_bucket')
class LeakyBucketThrottle(ThrottleStrategy):
  """
  漏桶限速：严格匀速输出，不允许突发。

  以 speed_kbps 恒定速率输出数据，从第一个 chunk 起即按速率等待。
  适合需要严格恒定速率、不允许任何突发的场景。
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
    self._rate: float = speed_kbps * 1024.0

  def create_reader(self, file_path: str, start: int, length: int) -> _LeakyBucketReader:
    return _LeakyBucketReader(
      file_path, start, length,
      self._chunk_size, self._rate, self._max_delay,
    )


def create_throttle(
    strategy: str,
    speed_kbps: int,
    max_delay: float,
    **kwargs: Any,
) -> Optional[ThrottleStrategy]:
  """
  工厂函数：按策略名创建限速策略实例。

  参数：
    strategy: 策略名（'chunk_sleep' / 'small_chunk' / 'token_bucket' / 'leaky_bucket'）
    speed_kbps: 限速速率（KB/s）
    max_delay: 单次延时上限（秒）
    **kwargs: 策略特定参数（如 chunk_size、burst_seconds）

  返回：
    ThrottleStrategy 实例；策略名未找到或创建异常时返回 None
  """
  cls = _STRATEGY_REGISTRY.get(strategy)
  if cls is None:
    APP_LOGGER.error(
      f'未知的限速策略：{strategy}，可用策略：{list(_STRATEGY_REGISTRY.keys())}'
    )
    return None
  try:
    return cls(speed_kbps=speed_kbps, max_delay=max_delay, **kwargs)
  except Exception as e:
    APP_LOGGER.error(f'限速策略创建异常：{strategy}，错误：{e}')
    return None
