# -*- coding: utf-8 -*-
import os


def is_dir_path_valid(dir_path: str) -> bool:
  """检查文件夹地址是否合法"""
  if type(dir_path) != str:
    return False

  # 地址存在并且是文件夹的地址
  return os.path.exists(dir_path) and os.path.isdir(dir_path)


def is_file_path_valid(file_path: str) -> bool:
  """检查文件地址是否合法"""
  if type(file_path) != str:
    return False

  # 地址存在并且是文件的地址
  return os.path.exists(file_path) and os.path.isfile(file_path)
