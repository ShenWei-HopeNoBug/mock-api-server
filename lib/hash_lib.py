# -*- coding: utf-8 -*-
import hashlib
import os
from typing import Optional


def get_file_hash(file_path: str, hash_algorithm: str = 'md5') -> Optional[str]:
  """
  生成文件的哈希字符串

  Args:
      file_path: 文件路径
      hash_algorithm: 哈希算法，支持 'md5', 'sha1', 'sha256', 'sha512' 等

  Returns:
      Optional[str]: 文件的哈希字符串，如果文件不存在或读取错误则返回None
  """
  if not os.path.isfile(file_path):
    return None

  try:
    # 创建哈希对象
    hash_obj = hashlib.new(hash_algorithm)

    # 以二进制模式分块读取文件
    with open(file_path, 'rb') as f:
      # 每次读取 64KB
      for chunk in iter(lambda: f.read(65536), b''):
        hash_obj.update(chunk)

    # 返回十六进制格式的哈希字符串
    return hash_obj.hexdigest()

  except (IOError, ValueError) as e:
    print(f"生成文件哈希时出错: {e}")
    return None


# 使用示例
if __name__ == "__main__":
  # 示例：计算文件的 SHA-256 哈希
  file_path = r"B:\project\pycharm\mock-api-server\server\data\static.json"  # 替换为你的文件路径
  hash_str = get_file_hash(file_path)

  if hash_str:
    print(f"文件 {file_path} 的哈希值为: \n{hash_str}")
  else:
    print(f"无法生成文件 {file_path} 的哈希值")
