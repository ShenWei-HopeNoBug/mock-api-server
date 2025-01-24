# -*- coding: utf-8 -*-
from decorate import error_catch
import json

global_file_path = './global_var.json'


def init(file=global_file_path):
  global_dict = {
    "client_exit": False,  # 是否已经退出程序
    "mitmproxy_stop_signal": False,  # 抓包停止信号
  }

  with open(file, 'w', encoding='utf-8') as fl:
    fl.write(json.dumps(global_dict))


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
    fl.write(json.dumps(global_dict))
