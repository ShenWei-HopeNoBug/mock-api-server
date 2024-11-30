# -*- coding: utf-8 -*-
import os
import hashlib
from urllib.parse import urlparse
import json
import threading
import psutil


# 获取字符串的 md5
def create_md5(string=''):
  return hashlib.md5(str(string).encode('utf-8')).hexdigest()


# 去掉链接里面的域名
def remove_url_domain(url=''):
  parse_data = urlparse(url)
  return parse_data.path


# 检查并创建文件夹
def check_and_create_dir(path):
  if not os.path.exists(path):
    os.makedirs(path)


class JsonFormat:
  # 格式化 json string 数据(业务映射)
  @staticmethod
  def format_json_string(json_string):
    return json.dumps(json.loads(json_string), ensure_ascii=False)

  # 格式化 dict 数据(业务映射)
  @staticmethod
  def format_dict(dict_data):
    return json.loads(json.dumps(dict_data, ensure_ascii=False))

  # 将字典转化成标准的 json string 数据(业务映射)
  @staticmethod
  def format_dict_to_json_string(dict_data):
    return json.dumps(dict_data, ensure_ascii=False)


# 线程装饰器
def create_thread(func):
  def wrapper(*args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.start()

  return wrapper


# 找到监听指定 ip 和 端口号的进程列表
def find_connection_process(ip='0.0.0.0', port=5000):
  process_list = []
  connections = psutil.net_connections()
  for conn in connections:
    if not conn.status == 'LISTEN':
      continue

    laddr = conn.laddr
    # 匹配指定 ip 和 端口号的进程
    if port == laddr.port and ip == laddr.ip:
      # 杀掉本地服务进程
      proc = psutil.Process(conn.pid)
      process_list.append(proc)

  return process_list
