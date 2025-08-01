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
import datetime
import uuid


# 修复字典数据参数
def fix_dict_field(dict_data: dict, fields: list) -> dict:
  if type(dict_data) != dict:
    return {}

  record: dict = {}
  for field in fields:
    key = field.get('key')
    if not key:
      continue

    default_callback = field.get('default_callback')
    default_value = default_callback() if callable(default_callback) else None
    value = dict_data.get(key, default_value)
    # 键名为 id 的情况下要做进一步校验
    if key == 'id' and (type(value) != str or not len(value)):
      value = default_value

    record[key] = value

  return record


# 生成数据的 uuid
def generate_uuid() -> str:
  name = '{}-{}'.format(uuid.uuid4(), uuid.uuid1())
  return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


# 限制数值范围
def limit_num_range(
    num: int or float,
    min_limit: int or float,
    max_limit: int or float
) -> int or float:
  if num > max_limit:
    return max_limit
  elif num < min_limit:
    return min_limit
  else:
    return num


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


# 生成时间戳
def create_timestamp(time_format: str = '%Y%m%d%H%M%S'):
  return datetime.datetime.now().strftime(time_format)


# 获取链接的域名
def get_url_domain(url: str = ''):
  domain = urlparse(url).netloc
  return domain


# 去掉链接里面的域名
def remove_url_domain(url: str = ''):
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
  # 将数据格式化为标准的 json string
  @staticmethod
  def dumps(data: dict or list) -> str:
    return json.dumps(data, ensure_ascii=False)

  # 格式化 json string 数据(业务映射)
  @staticmethod
  def format_json_string(json_string: str):
    return JsonFormat.dumps(json.loads(json_string))

  # 格式化 dict 数据(业务映射)
  @staticmethod
  def format_dict(dict_data: dict) -> dict:
    return json.loads(JsonFormat.dumps(dict_data))

  @staticmethod
  def sort_dumps(data: dict or list) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)

  @staticmethod
  def format_and_sort_json_string(json_string: str) -> str:
    return JsonFormat.sort_dumps(json.loads(json_string))

  @staticmethod
  def format_and_sort_dict(dict_data: dict) -> dict:
    return json.loads(JsonFormat.sort_dumps(dict_data))


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


# 配置文件管理器
class ConfigFileManager:
  def __init__(self, path: str, config: dict = None):
    self.path = path
    self.config = copy.deepcopy(config or {})

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
  def get(self, key: str) -> any:
    if not key:
      return None

    with open(self.path, 'r', encoding='utf-8') as fl:
      data = fl.read()
      dict_data: dict = json.loads(data)

    return dict_data.get(key, None)

  @error_catch(error_msg='更新变量失败！')
  def set(self, key: str, value: any):
    if not key:
      return

    with open(self.path, 'r', encoding='utf-8') as fl:
      data: str = fl.read()
      dict_data: dict = json.loads(data)
      dict_data[key] = value

    with open(self.path, 'w', encoding='utf-8') as fl:
      fl.write(JsonFormat.dumps(dict_data))

  @error_catch(error_msg='列表数据 get 失败', error_return=[])
  def get_list(self, key: str) -> list:
    list_data = self.get(key=key)
    # 数据类型校验
    if not type(list_data) is list:
      return []

    return list_data

  # 为 list 类型的数据 append 新数据，返回操作是否成功状态
  @error_catch(error_msg='列表数据 append 失败', error_return=False)
  def append_list_value(self, key: str, value: any, check_repeat=True) -> bool:
    list_data = self.get(key=key)
    # 数据类型校验
    if not type(list_data) is list:
      return False

    # 检查数据是否重复
    list_set = set(list_data)
    if check_repeat and value in list_set:
      return False

    list_data.append(value)
    self.set(key=key, value=list_data)
    return True

  # 为 list 类型的数据更新指定 index 数据，返回操作是否成功状态
  @error_catch(error_msg='列表数据 update 失败', error_return=False)
  def update_list_value(self, key: str, value: any, index: int = -1, check_repeat=True) -> bool:
    list_data = self.get(key=key)
    # 数据类型校验
    if not type(list_data) is list:
      return False

    # 索引范围校验
    if index < 0 or index >= len(list_data):
      return False

    # 检查数据是否重复
    list_set = set(list_data)
    if check_repeat and value in list_set:
      return False

    list_data[index] = value
    self.set(key=key, value=list_data)
    return True

  # 为 list 类型的数据删除指定 index 数据，返回操作是否成功状态
  @error_catch(error_msg='列表数据 delete 失败', error_return=False)
  def delete_list_value(self, key: str, index: int = -1) -> bool:
    list_data = self.get(key=key)
    # 数据类型校验
    if not type(list_data) is list:
      return False

    # 索引范围校验
    if index < 0 or index >= len(list_data):
      return False

    del list_data[index]
    self.set(key=key, value=list_data)
    return True

  # 清空指定 key 的 list 类型的数据
  @error_catch(error_msg='列表数据 clear 失败', error_return=False)
  def clear_list_value(self, key: str) -> bool:
    list_data = self.get(key=key)
    # 数据类型校验
    if not type(list_data) is list:
      return False

    self.set(key=key, value=[])
    return True


# 校验链接是否满足匹配条件
@error_catch(error_msg='校验链接是否满足匹配条件失败', error_return=False)
def is_url_match(url: str, includes: list or str) -> bool:
  # 入参校验
  if not len(url) or not len(includes):
    return False

  # 校验规则为字符串
  if type(includes) == str:
    include_reg = re.compile(includes)
    return bool(include_reg.search(url))
  # 校验规则为字符串列表
  elif type(includes) == list:
    pattern = r'({})'.format('|'.join(includes))
    include_reg = re.compile(pattern)
    return bool(include_reg.search(url))
  else:
    return False
