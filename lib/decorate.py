# -*- coding: utf-8 -*-
import asyncio
import copy
import threading
import datetime
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

from lib.logger_lib import APP_LOGGER

T = TypeVar('T')


# 异常捕获
def error_catch(
    func: Optional[Callable[..., T]] = None,
    *,
    error_msg: str = '',
    error_return: Any = None,
    log: bool = True,
) -> Union[Callable[..., T], Callable[[Callable[..., T]], Callable[..., T]]]:
  """
  异常捕获装饰器，捕获被装饰函数抛出的 Exception，返回 error_return 兜底值

  同时支持同步函数与异步函数（async def）：
    - 同步函数：通过 try/except 直接捕获调用期间的异常
    - 异步函数：通过 asyncio.iscoroutinefunction 识别后使用 async wrapper，
      在 await 执行期间捕获异常（同步 wrapper 只能捕获协程对象创建阶段的异常，
      无法捕获 await 期间的异常）

  注意：仅捕获 Exception 子类，不捕获 BaseException（如 asyncio.CancelledError、
  KeyboardInterrupt、SystemExit 等），这些异常会正常向上传播

  支持两种用法：
    @error_catch                                           # 无参，默认 error_return=None, log=True
    @error_catch(error_msg='xxx', error_return=[], log=False)  # 带参

  :param func: 被装饰函数（无参用法时由 Python 自动传入）
  :param error_msg: 自定义错误信息，为空时使用 'Error'
  :param error_return: 异常时返回的兜底值，会做 deepcopy
  :param log: 是否通过 APP_LOGGER 记录异常日志
  """

  def _make_wrapper(_func: Callable[..., T]) -> Callable[..., T]:
    # 异步函数分支：asyncio.iscoroutinefunction 可识别所有 async def 函数
    # 使用 async wrapper + await 才能捕获协程执行期间抛出的异常
    if asyncio.iscoroutinefunction(_func):
      @wraps(_func)
      async def async_wrapper(*args: Any, **kwargs: Any) -> T:
        try:
          return await _func(*args, **kwargs)
        except Exception as e:
          if log:
            message = error_msg or 'Error'
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            APP_LOGGER.error(f'[{current_time}] ERROR {message}：{e}')
          return copy.deepcopy(error_return)

      return async_wrapper

    # 同步函数分支
    @wraps(_func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
      try:
        return _func(*args, **kwargs)
      except Exception as e:
        if log:
          message = error_msg or 'Error'
          current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
          APP_LOGGER.error(f'[{current_time}] ERROR {message}：{e}')
        return copy.deepcopy(error_return)

    return wrapper

  # 无参用法：@error_catch
  if func is not None:
    return _make_wrapper(func)

  # 带参用法：@error_catch(error_msg='xxx', ...)
  return _make_wrapper


# 线程装饰器
def create_thread(
    func: Optional[Callable[..., Any]] = None,
    *,
    daemon: bool = False,
) -> Union[Callable[..., None], Callable[[Callable[..., Any]], Callable[..., None]]]:
  """
  线程装饰器，将被装饰函数放入新线程中执行，不阻塞调用方

  支持两种用法：
    @create_thread                        # 无参，默认 daemon=False
    @create_thread(daemon=True)           # 带参，指定守护线程

  :param func: 需要异步执行的函数（无参用法时由 Python 自动传入）
  :param daemon: 是否作为守护线程运行，守护线程不会阻止主进程退出
  """

  def _make_wrapper(_func: Callable[..., Any]) -> Callable[..., None]:
    @wraps(_func)
    def wrapper(*args: Any, **kwargs: Any) -> None:
      thread = threading.Thread(target=_func, args=args, kwargs=kwargs, daemon=daemon)
      thread.start()

    return wrapper

  # 无参用法：@create_thread
  if func is not None:
    return _make_wrapper(func)

  # 带参用法：@create_thread(daemon=True)
  return _make_wrapper
