# -*- coding: utf-8 -*-
import os
import re
import copy
import hashlib
from urllib.parse import urlparse
import json
import psutil
from PIL import Image
import socket
from lib.decorate import error_catch


# 获取本机 ip 地址
def get_ip_address():
  # 获取主机名
  hostname = socket.gethostname()
  # 获取IP地址
  ip_address = socket.gethostbyname(hostname)
  return ip_address


# 获取字符串的 md5
def create_md5(string=''):
  return hashlib.md5(str(string).encode('utf-8')).hexdigest()


# 去掉链接里面的域名
def remove_url_domain(url=''):
  parse_data = urlparse(url)
  return parse_data.path


# 去掉链接里面的 query 参数
def remove_url_query(url=''):
  return re.sub(r'\?.*$', '', url)


# 检查并创建文件夹
def check_and_create_dir(path):
  if not os.path.exists(path):
    os.makedirs(path)


@error_catch(error_msg='是否为文件请求判断失败', error_return=False)
def is_file_request(url=''):
  # 去掉 query 参数的请求
  pure_url = url.split(r'?')[0]
  # 去掉协议头
  pure_url = re.sub(r'https?://', '', pure_url)
  # 判断是否有子路径
  if re.search(r'/', pure_url):
    last_route = pure_url.split(r'/')[-1]
    # 末尾路由带.的判断为文件请求
    return bool(re.search(r'\.', last_route))
  else:
    return False


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

  # 将数据格式化为标准的 json string
  @staticmethod
  def dumps(data):
    return json.dumps(data, ensure_ascii=False)


# 找到监听指定 ip 和 端口号网络服务的进程列表
@error_catch(error_msg='查找服务进程失败', error_return=[])
def find_connection_process(ip='0.0.0.0', port=5000):
  process_list = []
  connections = psutil.net_connections()
  for conn in connections:
    if not conn.status == 'LISTEN':
      continue

    laddr = conn.laddr
    # 匹配指定 ip 和 端口号的进程
    if port == laddr.port and ip == laddr.ip:
      # 本地服务进程
      proc = psutil.Process(conn.pid)
      process_list.append(proc)

  return process_list


# 检测本地指定 ip 和 端口号网络服务是否已经被占用
def check_local_connection(ip='0.0.0.0', port=5000):
  connections = psutil.net_connections()
  for conn in connections:
    if not conn.status == 'LISTEN':
      continue

    laddr = conn.laddr
    # 匹配指定 ip 和 端口号的进程
    if port == laddr.port and ip == laddr.ip:
      return True

  return False


# 压缩图片
@error_catch(error_msg='压缩图片时出错', error_return=False)
def compress_image(input_path, output_path, quality=80):
  img_excepts = ['.png', '.jpg', '.jpeg']
  img_pattern = r'({})$'.format('|'.join(img_excepts))
  img_compare = re.compile(img_pattern, flags=re.IGNORECASE)

  if len(img_compare.findall(input_path)) == 0:
    print('待压缩图片文件格式不支持：{}'.format(input_path))
    return False

  if not os.path.isfile(input_path):
    print('待压缩图片不存在：{}'.format(input_path))
    return False

  with Image.open(input_path) as img:
    # png 压缩
    if input_path.lower().endswith('.png'):
      img = img.quantize(colors=256)
      img.save(output_path)
    else:
      # jpg 压缩
      img.save(output_path, quality=quality)
  return True


class ConfigFileManager:
  def __init__(self, path: str, config: dict = {}):
    self.path = path
    self.config = copy.deepcopy(config)

  def init(self, replace: bool = False):
    work_dir = os.path.dirname(self.path)
    # 检查并创建系统文件夹
    check_and_create_dir(work_dir)

    # 不替换已经存在的文件
    if not replace and os.path.exists(self.path):
      return

    with open(self.path, 'w', encoding='utf-8') as fl:
      fl.write(JsonFormat.dumps(copy.deepcopy(self.config)))

  @error_catch(error_msg='查找变量失败！', error_return=None)
  def get(self, key: str):
    if not key:
      return None

    with open(self.path, 'r', encoding='utf-8') as fl:
      data = fl.read()
      dict_data: dict = json.loads(data)

    return dict_data.get(key, None)

  @error_catch(error_msg='更新变量失败！')
  def set(self, key: str, value):
    if not key:
      return

    with open(self.path, 'r', encoding='utf-8') as fl:
      data: str = fl.read()
      dict_data: dict = json.loads(data)
      dict_data[key] = value

    with open(self.path, 'w', encoding='utf-8') as fl:
      fl.write(JsonFormat.dumps(dict_data))
