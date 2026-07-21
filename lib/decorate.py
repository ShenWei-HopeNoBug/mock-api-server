# -*- coding: utf-8 -*-
import copy
import threading
import datetime
from functools import wraps
from typing import Any, Callable, TypeVar

from lib.logger_lib import APP_LOGGER

T = TypeVar('T')


# 异常捕获
def error_catch(
    error_msg: str = '',
    error_return: Any = None,
    log: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
  """
  异常捕获装饰器，捕获被装饰函数抛出的 Exception，返回 error_return 兜底值

  :param error_msg: 自定义错误信息，为空时使用 'Error'
  :param error_return: 异常时返回的兜底值，会做 deepcopy
  :param log: 是否通过 APP_LOGGER 记录异常日志
  """

  def decorate(func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
      try:
        return func(*args, **kwargs)
      except Exception as e:
        if log:
          message = error_msg or 'Error'
          current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
          APP_LOGGER.error(f'[{current_time}] ERROR {message}：{e}')
        return copy.deepcopy(error_return)

    return wrapper

  return decorate


# 线程装饰器
def create_thread(func: Callable[..., Any]) -> Callable[..., None]:
  """
  线程装饰器，将被装饰函数放入新线程中执行，不阻塞调用方

  :param func: 需要异步执行的函数
  """

  @wraps(func)
  def wrapper(*args: Any, **kwargs: Any) -> None:
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.start()

  return wrapper
