# -*- coding: utf-8 -*-
import os
from lib.utils_lib import (check_and_create_dir, JsonFormat)
from config.work_file import (DEFAULT_WORK_DIR, WORK_DIR_DICT, WORK_FILE_DICT)


# 检查工作目录文件完整性
def check_work_files(work_dir=DEFAULT_WORK_DIR):
  dir_path_list = [r'{}{}'.format(
    work_dir,
    detail.get('path')
  ) for detail in WORK_DIR_DICT.values()]
  file_path_list = [r'{}{}'.format(
    work_dir,
    detail.get('path')
  ) for detail in WORK_FILE_DICT.values()]
  check_path_list = [work_dir, *dir_path_list, *file_path_list]

  valid = True
  # 文件完整性检查
  for path in check_path_list:
    if not os.path.exists(path):
      valid = False
      break

  return valid


# 创建工作目录文件
def create_work_files(work_dir=DEFAULT_WORK_DIR):
  dir_path_list = [r'{}{}'.format(
    work_dir,
    detail.get('path'),
  ) for detail in WORK_DIR_DICT.values()]
  check_dir_list = [work_dir, *dir_path_list]
  # 批量检查和创建目录
  for dir_path in check_dir_list:
    check_and_create_dir(dir_path)

  # 批量检查和创建文件
  for file_detail in WORK_FILE_DICT.values():
    file_path = r'{}{}'.format(work_dir, file_detail.get('path'))
    # 文件默认数据
    default_data = file_detail.get('default')

    # 文件不存在时创建默认文件
    if not os.path.exists(file_path):
      with open(file_path, 'w', encoding='utf-8') as fl:
        fl.write(JsonFormat.dumps(default_data))


if __name__ == '__main__':
  res = check_work_files()
  print(res)
