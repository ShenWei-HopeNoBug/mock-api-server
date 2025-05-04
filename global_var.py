# -*- coding: utf-8 -*-
from decorate import error_catch
import json
from utils import check_and_create_dir, JsonFormat

# 版本号
version = 'v0.0.2'
# mitmproxy 抓包默认配置
mitmproxy_config = {
  "include_path": "www.baidu.com",
}

'''
mock 服务的配置
include_files: 启动服务后要动态替换的静态资源链接扩展名列表
'''
mock_server_config = {
  "include_files": [".png", ".jpg", ".jpeg", ".gif", ".avif", ".webp", ".npy"],
}

# 存放数据文件的目录
data_dir_path = r'/data'
# 存放配置文件的目录
config_dir_path = r'/config'
# 存放系统文件的目录
system_dir_path = r'./system'
# 默认全局变量文件地址
global_file_path = '{}/globals.json'.format(system_dir_path)


def init(file=global_file_path):
  # 检查并创建系统文件夹
  check_and_create_dir(system_dir_path)

  global_dict = {
    "client_exit": False,  # 是否已经退出程序
    "mitmproxy_stop_signal": False,  # 抓包停止信号
  }

  with open(file, 'w', encoding='utf-8') as fl:
    fl.write(JsonFormat.format_dict_to_json_string(global_dict))


@error_catch(error_msg='查找全局变量失败！', error_return=None)
def get_global_var(file=global_file_path, key=''):
  with open(file, 'r', encoding='utf-8') as fl:
    data = fl.read()
    global_dict = json.loads(data)

  return global_dict[key]


@error_catch(error_msg='更新全局变量失败！')
def update_global_var(file=global_file_path, key='', value=None):
  with open(file, 'r', encoding='utf-8') as fl:
    data = fl.read()
    global_dict = json.loads(data)
    global_dict[key] = value

  with open(file, 'w', encoding='utf-8') as fl:
    fl.write(JsonFormat.format_dict_to_json_string(global_dict))
