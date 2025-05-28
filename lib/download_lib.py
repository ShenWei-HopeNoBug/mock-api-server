# -*- coding: utf-8 -*-
import os
import json
import shutil
from config.work_file import STATIC_DIR
from lib.decorate import error_catch
from lib.utils_lib import check_and_create_dir, create_timestamp


@error_catch(error_msg='获取导出下载地址列表失败', error_return=[])
def get_output_data_list(log_path: str, work_dir: str = '.'):
  # 检查下载日志路径
  if not os.path.exists(log_path):
    return []

  static_dir = r'{}{}'.format(work_dir, STATIC_DIR)
  # 检查静态资源目录
  if not os.path.exists(static_dir):
    return []

  with open(log_path, 'r', encoding='utf-8') as fl:
    logs = json.loads(fl.read())

  path_list = []
  for log in logs:
    success = log.get('success', False)
    file_name = log.get('file_name', '')
    static_path = os.path.abspath(r'{}/{}'.format(static_dir, file_name))

    # 下载成功且静态资源目录有这个文件，添加到导出列表中
    if success and os.path.exists(static_path):
      path_list.append({
        "path": static_path,
        "file_name": file_name,
      })

  return path_list


@error_catch(error_msg='导出静态资源失败', error_return=[])
def output_static_files(output_dir='./output', output_list=[]):
  if not len(output_list):
    return

  # 拼接导出文件夹路径
  save_dir = os.path.abspath(r'{}/output-static-{}'.format(
    output_dir,
    create_timestamp(),
  ))

  # 检查并创建导出路径
  check_and_create_dir(save_dir)
  for output_data in output_list:
    path = output_data.get('path')
    file_name = output_data.get('file_name', '')
    if not (path and file_name and os.path.exists(path)):
      continue

    # 复制静态资源到目标文件夹
    shutil.copy(path, save_dir)
