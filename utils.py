# -*- coding: utf-8 -*-
import os
import re
import hashlib
from urllib.parse import urlparse
import json
import psutil
from PIL import Image
from decorate import error_catch
import socket
import global_var
import pandas as pd
import webbrowser


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


# 检查并创建文件夹
def check_and_create_dir(path):
  if not os.path.exists(path):
    os.makedirs(path)


@error_catch(error_msg='判断是否为文件请求失败', error_return=False)
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


@error_catch(error_msg='读取 mitmproxy api 数据失败', error_return=[])
def get_mitmproxy_api_data_list(work_dir='.'):
  api_list = []
  # 数据源地址
  mitmproxy_data_path = '{}{}/output.json'.format(work_dir, global_var.data_dir_path)
  # 读取抓包数据
  if os.path.exists(mitmproxy_data_path):
    data = pd.read_json(mitmproxy_data_path)

    # 行遍历
    for row_index, row_data in data.iterrows():
      api_list.append({
        "type": row_data.get('type'),
        "url": row_data.get('url'),
        "method": row_data.get('method'),
        "params": row_data.get('params'),
        "response": row_data.get('response'),
      })

  return api_list


@error_catch(error_msg='读取 user api 数据失败', error_return=[])
def get_user_api_data_list(work_dir='.'):
  # 读取用户手动 mock 的接口数据
  user_data_path = '{}{}/user_api.json'.format(work_dir, global_var.data_dir_path)
  if not os.path.exists(user_data_path):
    return []

  with open(user_data_path, 'r', encoding='utf-8') as fl:
    user_api_list = json.loads(fl.read())
    return user_api_list


@error_catch(error_msg='读取 api 数据文件失败', error_return=[])
def get_mock_api_data_list(work_dir='.'):
  api_list = get_mitmproxy_api_data_list(work_dir=work_dir)
  api_list.extend(get_user_api_data_list(work_dir=work_dir))

  return api_list


# 加工并打开抓包数据预览html
@error_catch(error_msg='打开抓包数据预览html失败', error_return=False)
def open_mitmproxy_preview_html(root_dir='.', work_dir='.'):
  # 预览数据列表
  preview_list = get_mock_api_data_list(work_dir=work_dir)

  # 把预览数据写入web的静态资源文件
  web_mitmproxy_output_file = r'{}/web/mitmproxy_output.js'.format(root_dir)
  if not os.path.exists(web_mitmproxy_output_file):
    return False
  with open(web_mitmproxy_output_file, 'w', encoding='utf-8') as fl:
    content = "window.MITMPROXY_OUTPUT = {}\n".format(
      JsonFormat.format_dict_to_json_string(preview_list),
    )
    fl.write(content)

  preview_html = r'{}/web/apps/dataPreview/index.html'.format(root_dir)
  if not os.path.exists(preview_html):
    return False
  # 用浏览器打开预览 html 文件
  webbrowser.open(os.path.abspath(preview_html))

  return True
