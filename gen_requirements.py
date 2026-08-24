# -*- coding: utf-8 -*-
"""调用 pipreqs 扫描项目依赖，生成 requirements 文件

用法：
  python gen_requirements.py                  # 输出到 requirements.txt
  python gen_requirements.py -o package.txt   # 输出到指定文件

与 pip freeze 不同，只提取代码中实际 import 的第三方包。
"""
import argparse
import os
import subprocess
import sys

# 需要排除的目录（参考 .gitignore + 虚拟环境 + 构建产物）
IGNORE_DIRS = [
  '.venv', '.git', '__pycache__', 'build', 'dist', 'node_modules',
  '.idea', '.vscode', 'logs', 'appServer', 'system', 'static',
  'server', 'web', 'resources', 'assets',
]


def main():
  parser = argparse.ArgumentParser(description='调用 pipreqs 扫描项目依赖')
  parser.add_argument('-o', '--output', default='requirements.txt',
                      help='输出文件路径（默认 requirements.txt）')
  args = parser.parse_args()

  root = os.path.dirname(os.path.abspath(__file__))
  output_path = os.path.join(root, args.output)

  pipreqs_bin = os.path.join(os.path.dirname(sys.executable), 'pipreqs.exe')
  if not os.path.exists(pipreqs_bin):
    # Linux/macOS fallback
    pipreqs_bin = os.path.join(os.path.dirname(sys.executable), 'pipreqs')

  cmd = [
    pipreqs_bin,
    root,
    '--ignore', ','.join(IGNORE_DIRS),
    '--encoding', 'utf-8',
    '--force',
    '--savepath', output_path,
  ]

  print(f'扫描目录：{root}')
  print(f'排除目录：{IGNORE_DIRS}')
  print(f'输出文件：{output_path}\n')

  result = subprocess.run(cmd)
  if result.returncode != 0:
    sys.exit(result.returncode)

  print(f'\n完成：{output_path}')


if __name__ == '__main__':
  main()
