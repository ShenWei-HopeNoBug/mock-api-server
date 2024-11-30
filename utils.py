# -*- coding: utf-8 -*-
import os
import re
import hashlib
from urllib.parse import urlparse
import json
import psutil
from PIL import Image
from decorate import error_catch


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
      # 杀掉本地服务进程
      proc = psutil.Process(conn.pid)
      process_list.append(proc)

  return process_list


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
