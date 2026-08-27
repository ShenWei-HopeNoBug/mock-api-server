# -*- coding: utf-8 -*-
import os
from typing import Optional
import hashlib
from lib.decorate import error_catch
import sys


def is_dir_path_valid(dir_path: str) -> bool:
  """检查文件夹地址是否合法"""
  if not isinstance(dir_path, str):
    return False

  # 地址存在并且是文件夹的地址
  return os.path.exists(dir_path) and os.path.isdir(dir_path)


def is_file_path_valid(file_path: str) -> bool:
  """检查文件地址是否合法"""
  if not isinstance(file_path, str):
    return False

  # 地址存在并且是文件的地址
  return os.path.exists(file_path) and os.path.isfile(file_path)


@error_catch(error_msg='生成文件hash异常', error_return=None)
def create_file_hash(file_path: str, hash_algorithm: str = 'md5', buffer_size: int = 65536) -> Optional[str]:
  if not is_file_path_valid(file_path):
    return None
  # 创建哈希对象
  hasher = hashlib.new(hash_algorithm)

  # 以二进制模式打开文件
  with open(file_path, 'rb') as f:
    # 分块读取文件内容并更新哈希值
    while chunk := f.read(buffer_size):
      hasher.update(chunk)

  # 返回十六进制格式的哈希值
  return hasher.hexdigest()


def diff_file(source_path: str, target_path: str) -> bool:
  """对比两个文件内容是否有差异"""
  if not is_file_path_valid(source_path) or not is_file_path_valid(target_path):
    return True

  source_hash = create_file_hash(source_path)
  target_hash = create_file_hash(target_path)

  return source_hash != target_hash


if __name__ == "__main__":
  sys.exit(0)
