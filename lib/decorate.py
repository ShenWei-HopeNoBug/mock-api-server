# -*- coding: utf-8 -*-
import copy
import threading
import datetime
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

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
