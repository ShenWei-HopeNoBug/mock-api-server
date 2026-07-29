# -*- coding: utf-8 -*-
import sys
import os
from PIL import Image


def main():
  from_path = '../app-icon.png'
  save_path = '../assets/app.ico'

  abs_from_path = os.path.abspath(from_path)
  abs_save_path = os.path.abspath(save_path)

  if not os.path.exists(abs_from_path):
    print(f'[ERROR] 源文件不存在: {abs_from_path}')
    sys.exit(1)
  if not os.path.isfile(abs_from_path):
    print(f'[ERROR] 源路径不是文件: {abs_from_path}')
    sys.exit(1)

  print(f'[INFO] 开始转换: {abs_from_path} -> {abs_save_path}')
  img = Image.open(abs_from_path)
  print(f'[INFO] 已打开图片: {abs_from_path}, 尺寸={img.size}')
  img.save(abs_save_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
  print(f'[INFO] ICO 文件已保存: {abs_save_path}')


if __name__ == '__main__':
  main()
  sys.exit(0)
