# -*- coding: utf-8 -*-
import threading


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
          print('{}：{}'.format(message, e))
        return error_return

    return wrapper

  return decorate


# 线程装饰器
def create_thread(func):
  def wrapper(*args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.start()

  return wrapper
