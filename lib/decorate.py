# -*- coding: utf-8 -*-
import copy
import threading
import datetime
from lib.logger_lib import APP_LOGGER


# 异常捕获
def error_catch(error_msg='', error_return=None, print_error_msg=True):
  def decorate(func):
    def wrapper(*args, **kwargs):
      try:
        return func(*args, **kwargs)
      except Exception as e:
        # 判断是否要打印日志
        if print_error_msg:
          message = error_msg or 'Error'
          current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
          APP_LOGGER.error(f'[{current_time}] ERROR {message}：{e}')
        return copy.deepcopy(error_return)

    return wrapper

  return decorate


# 线程装饰器
def create_thread(func):
  def wrapper(*args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.start()

  return wrapper
