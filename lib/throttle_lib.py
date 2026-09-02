# -*- coding: utf-8 -*-
"""
静态资源限速策略模块

提供统一的 ThrottleStrategy 接口，支持多种限速方案替换测试：
- chunk_sleep：固定 chunk + per-chunk sleep（脉冲式）
- token_bucket：令牌桶，允许短暂突发但长期匀速
- leaky_bucket：漏桶，严格匀速输出，不允许突发
- sliding_window：滑动窗口，精确控制单位时间传输上限
- progressive_delay：渐进式延迟，初始快速逐渐变慢（模拟网络恶化）
- random_jitter：随机抖动，在基础延迟上叠加随机波动

通过 create_throttle() 工厂函数按策略名创建，StaticFileHandler 只依赖接口，
切换策略时无需修改 StaticFileHandler 或 _serve_throttled。
"""
import random
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

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


class _SlidingWindowReader:
  """
  滑动窗口 file-like object，精确控制窗口内传输上限。

  维护一个 deque 记录窗口内每次读取的 (timestamp, bytes)，
  read() 前裁剪过期记录，若窗口内总量 + 本次读取超出上限则等待。
  单次等待不超过 max_delay。
  """

  def __init__(
      self,
      file_path: str,
      start: int,
      length: int,
      chunk_size: int,
      rate_bytes_per_sec: float,
      window_seconds: float,
      max_delay: float,
  ) -> None:
    self._f = open(file_path, 'rb')
    self._f.seek(start)
    self._remaining: int = length
    self._chunk_size: int = chunk_size
    self._rate: float = rate_bytes_per_sec
    self._window: float = window_seconds
    self._max_delay: float = max_delay
    self._max_bytes: float = rate_bytes_per_sec * window_seconds
    self._records: Deque[Tuple[float, int]] = deque()

  def _prune(self) -> None:
    cutoff = time.monotonic() - self._window
    while self._records and self._records[0][0] < cutoff:
      self._records.popleft()

  def read(self, size: int = -1) -> bytes:
    if self._remaining <= 0:
      return b''
    read_size: int = min(size if size > 0 else self._chunk_size, self._remaining, self._chunk_size)

    self._prune()
    window_bytes = sum(b for _, b in self._records)
    if window_bytes + read_size > self._max_bytes:
      deficit = window_bytes + read_size - self._max_bytes
      wait = min(deficit / self._rate, self._max_delay)
      time.sleep(wait)
      self._prune()

    data: bytes = self._f.read(read_size)
    if not data:
      self._remaining = 0
      return b''
    self._remaining -= len(data)
    self._records.append((time.monotonic(), len(data)))
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


class _ProgressiveDelayReader:
  """
  渐进式延迟 file-like object，初始快速逐渐变慢。

  per_chunk_delay 随传输进度从 base_delay * start_factor 线性增长到 base_delay * end_factor，
  模拟网络逐渐恶化（信号衰减、基站切换等）。
  单次延迟不超过 max_delay。
  """

  def __init__(
      self,
      file_path: str,
      start: int,
      length: int,
      chunk_size: int,
      base_delay: float,
      start_factor: float,
      end_factor: float,
      max_delay: float,
  ) -> None:
    self._f = open(file_path, 'rb')
    self._f.seek(start)
    self._remaining: int = length
    self._total: int = length
    self._chunk_size: int = chunk_size
    self._base_delay: float = base_delay
    self._start_factor: float = start_factor
    self._end_factor: float = end_factor
    self._max_delay: float = max_delay
    self._bytes_sent: int = 0

  def read(self, size: int = -1) -> bytes:
    if self._remaining <= 0:
      return b''
    read_size: int = min(size if size > 0 else self._chunk_size, self._remaining, self._chunk_size)

    progress: float = self._bytes_sent / self._total if self._total > 0 else 1.0
    factor: float = self._start_factor + (self._end_factor - self._start_factor) * progress
    delay: float = min(self._base_delay * factor, self._max_delay)
    if delay > 0:
      time.sleep(delay)

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


class _RandomJitterReader:
  """
  随机抖动 file-like object，在基础延迟上叠加随机波动。

  每次 read() 的延迟 = base_delay * random.uniform(1 - jitter, 1 + jitter)，
  模拟真实网络的 RTT 波动，避免机械式匀速。
  单次延迟不超过 max_delay。
  """

  def __init__(
      self,
      file_path: str,
      start: int,
      length: int,
      chunk_size: int,
      base_delay: float,
      jitter: float,
      max_delay: float,
  ) -> None:
    self._f = open(file_path, 'rb')
    self._f.seek(start)
    self._remaining: int = length
    self._chunk_size: int = chunk_size
    self._base_delay: float = base_delay
    self._jitter: float = jitter
    self._max_delay: float = max_delay

  def read(self, size: int = -1) -> bytes:
    if self._remaining <= 0:
      return b''
    read_size: int = min(size if size > 0 else self._chunk_size, self._remaining, self._chunk_size)

    delay: float = min(
      self._base_delay * random.uniform(1 - self._jitter, 1 + self._jitter),
      self._max_delay,
    )
    if delay > 0:
      time.sleep(delay)

    data: bytes = self._f.read(read_size)
    if not data:
      self._remaining = 0
      return b''
    self._remaining -= len(data)
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


@register_strategy('CHUNK_SLEEP')
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


@register_strategy('TOKEN_BUCKET')
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


@register_strategy('LEAKY_BUCKET')
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


@register_strategy('SLIDING_WINDOW')
class SlidingWindowThrottle(ThrottleStrategy):
  """
  滑动窗口限速：精确控制窗口内传输上限。

  维护 window_seconds（默认 1 秒）的时间窗口，
  窗口内传输总量不超过 speed_kbps * 1024 * window_seconds。
  比固定 chunk sleep 更精确控制单位时间传输量，窗口边界不会出现脉冲。
  """

  def __init__(
      self,
      speed_kbps: int,
      max_delay: float,
      chunk_size: int = 64 * 1024,
      window_seconds: float = 1.0,
  ) -> None:
    self._speed: int = speed_kbps
    self._max_delay: float = max_delay
    self._chunk_size: int = chunk_size
    self._rate: float = speed_kbps * 1024.0
    self._window: float = window_seconds

  def create_reader(self, file_path: str, start: int, length: int) -> _SlidingWindowReader:
    return _SlidingWindowReader(
      file_path, start, length,
      self._chunk_size, self._rate, self._window, self._max_delay,
    )


@register_strategy('PROGRESSIVE_DELAY')
class ProgressiveDelayThrottle(ThrottleStrategy):
  """
  渐进式延迟限速：初始快速，逐渐变慢。

  per_chunk_delay 随传输进度从 base_delay * start_factor 线性增长到 base_delay * end_factor，
  模拟网络逐渐恶化（信号衰减、基站切换等）。
  start_factor 默认 0.2（首屏 5 倍速），end_factor 默认 2.0（尾部半速）。
  """

  def __init__(
      self,
      speed_kbps: int,
      max_delay: float,
      chunk_size: int = 64 * 1024,
      start_factor: float = 0.2,
      end_factor: float = 2.0,
  ) -> None:
    self._speed: int = speed_kbps
    self._max_delay: float = max_delay
    self._chunk_size: int = chunk_size
    self._start_factor: float = start_factor
    self._end_factor: float = end_factor

  def create_reader(self, file_path: str, start: int, length: int) -> _ProgressiveDelayReader:
    chunk_kb: float = self._chunk_size / 1024
    base_delay: float = chunk_kb / self._speed
    return _ProgressiveDelayReader(
      file_path, start, length,
      self._chunk_size, base_delay, self._start_factor, self._end_factor, self._max_delay,
    )


@register_strategy('RANDOM_JITTER')
class RandomJitterThrottle(ThrottleStrategy):
  """
  随机抖动限速：在基础延迟上叠加随机波动。

  基础延迟与 chunk_sleep 相同（chunk_kb / speed_kbps），
  每次叠加 ±jitter 的随机波动（默认 ±30%），
  模拟真实网络的 RTT 波动，避免机械式匀速。
  """

  def __init__(
      self,
      speed_kbps: int,
      max_delay: float,
      chunk_size: int = 64 * 1024,
      jitter: float = 0.3,
  ) -> None:
    self._speed: int = speed_kbps
    self._max_delay: float = max_delay
    self._chunk_size: int = chunk_size
    self._jitter: float = jitter

  def create_reader(self, file_path: str, start: int, length: int) -> _RandomJitterReader:
    chunk_kb: float = self._chunk_size / 1024
    base_delay: float = chunk_kb / self._speed
    return _RandomJitterReader(
      file_path, start, length,
      self._chunk_size, base_delay, self._jitter, self._max_delay,
    )


# 策略名 → 中文名
_STRATEGY_LABELS: Dict[str, str] = {
  'CHUNK_SLEEP':       '固定分块休眠',
  'TOKEN_BUCKET':      '令牌桶',
  'LEAKY_BUCKET':      '漏桶',
  'SLIDING_WINDOW':    '滑动窗口',
  'PROGRESSIVE_DELAY': '渐进式延迟',
  'RANDOM_JITTER':     '随机抖动',
}


def get_strategy_options() -> list:
  """
  返回所有已注册限速策略的 (value, label) 列表。

  - value: 策略名，用于配置存储和 create_throttle() 调用
  - label: 显示文案，格式为 "英文名（中文名）"
  """
  return [
    (name, f'{name}（{_STRATEGY_LABELS.get(name, name)}）')
    for name in _STRATEGY_REGISTRY
  ]


def create_throttle(
    strategy: str,
    speed_kbps: int,
    max_delay: float,
    **kwargs: Any,
) -> Optional[ThrottleStrategy]:
  """
  工厂函数：按策略名创建限速策略实例。

  参数：
    strategy: 策略名（'CHUNK_SLEEP' / 'TOKEN_BUCKET' / 'LEAKY_BUCKET' /
             'SLIDING_WINDOW' / 'PROGRESSIVE_DELAY' / 'RANDOM_JITTER'）
    speed_kbps: 限速速率（KB/s）
    max_delay: 单次延时上限（秒）
    **kwargs: 策略特定参数（如 chunk_size、burst_seconds、window_seconds、
             start_factor、end_factor、jitter）

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
