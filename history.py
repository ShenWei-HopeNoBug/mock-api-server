# -*- coding: utf-8 -*-
import os
from decorate import error_catch
import json
import global_var
from utils import check_and_create_dir

# 默认历史数据文件地址
history_file_path = '{}/history.json'.format(global_var.system_dir_path)


def init(file=history_file_path):
  # 文件已创建，跳过
  if os.path.exists(file):
    return

  # 检查并创建系统文件夹
  check_and_create_dir(global_var.system_dir_path)

  history_dict = {
    "work_dir": "./server",  # app 工作目录
  }

  with open(file, 'w', encoding='utf-8') as fl:
    fl.write(json.dumps(history_dict))


@error_catch(error_msg='查找历史数据失败！', error_return=None)
def get_history_var(file=history_file_path, key=''):
  with open(file, 'r', encoding='utf-8') as fl:
    data = fl.read()
    history_dict = json.loads(data)

  return history_dict[key]


@error_catch(error_msg='更新历史数据失败！')
def update_history_var(file=history_file_path, key='', value=None):
  with open(file, 'r', encoding='utf-8') as fl:
    data = fl.read()
    history_dict = json.loads(data)
    history_dict[key] = value

  with open(file, 'w', encoding='utf-8') as fl:
    fl.write(json.dumps(history_dict))
