import threading


# 异常捕获
def error_catch(error_msg='', error_return=None):
  def decorate(func):
    def wrapper(*args, **kwargs):
      try:
        return func(*args, **kwargs)
      except Exception as e:
        message = error_msg or 'error'
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
