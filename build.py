# -*- coding: utf-8 -*-
import subprocess
from config import globals
import os
import json
import shutil
from lib.utils_lib import create_timestamp

BUILD_CONFIG_FILE = './build_config.json'


def generate_build_config(mitmproxy_log, version):
  """生成构建配置 JSON，打包时通过 --add-data 注入到 exe 中"""
  config = {
    'MITMPROXY_LOG': mitmproxy_log,
    'VERSION': version,
  }
  with open(BUILD_CONFIG_FILE, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
  print(f'写入构建配置：\n{json.dumps(config, indent=2, ensure_ascii=False)}')


'''
打包应用
@:param window -打包的应用是否带黑窗
@:param timestamp -打包应用名带的时间戳
'''


def app_build(window=False, timestamp=''):
  # 当前版本号
  version = globals.version
  win_ext = '.win' if window else ''
  time_ext = f'.{timestamp}' if timestamp else ''
  # 版本tag
  app_version_tag = f'{version}-{timestamp}' if timestamp else version
  app_name = f'mockServer{win_ext}{time_ext}-{version}'

  # 生成此变体的构建配置
  generate_build_config(mitmproxy_log=window, version=app_version_tag)

  args = [
    "pyinstaller",
    f"--name={app_name}",
    f"--contents-directory=site-packages",
    "--add-data", "schema;schema/",
    "--add-data", f"{BUILD_CONFIG_FILE};.",
    "main.py",
    "-D",
  ]
  # 打包命令加上黑窗
  if not window:
    args.append("-w")

  # 开始打包
  subprocess.run(args)

  spec_file = f'./{app_name}.spec'
  if os.path.exists(spec_file):
    os.remove(spec_file)
    print(f'删除文件：{spec_file}')

  # 删除临时的打包文件夹
  build_tmp_dir = './build'
  if os.path.exists(build_tmp_dir):
    shutil.rmtree(build_tmp_dir)
    print(f'删除文件夹：{build_tmp_dir}')

  return {
    "app_name": app_name,
    "version": version,
  }


# 批量打包
def batch_build():
  current = create_timestamp('%Y%m%d%H%M%S')
  # 带黑窗打包
  win_build_info = app_build(window=True, timestamp=current)
  # 不带黑窗打包
  build_info = app_build(window=False, timestamp=current)

  win_build_app_name = win_build_info.get('app_name')
  build_app_name = build_info.get('app_name')

  # 将带黑窗的exe应用移动到不带黑窗的打包目录下
  win_build_app_dir = f'./dist/{win_build_app_name}'
  win_build_app_path = f'{win_build_app_dir}/{win_build_app_name}.exe'
  move_dir = f'./dist/{build_app_name}'

  path_valid = os.path.exists(move_dir) and os.path.exists(win_build_app_path)
  print(f'路径检测：\n ---> from：{win_build_app_path}  \n ---> to：{move_dir} \n valid：{path_valid}')

  if os.path.exists(move_dir) and os.path.exists(win_build_app_path):
    print(f'开始移动打包产物：\n{win_build_app_path} -> {move_dir}')
    shutil.move(win_build_app_path, move_dir)
    print(f'删除文件夹：{win_build_app_dir}')
    shutil.rmtree(win_build_app_dir)

  # 清理临时构建配置
  if os.path.exists(BUILD_CONFIG_FILE):
    os.remove(BUILD_CONFIG_FILE)
    print(f'删除文件：{BUILD_CONFIG_FILE}')


if __name__ == '__main__':
  # 批量打包
  batch_build()

  # 调试打包
  # current = create_timestamp('%Y%m%d%H%M%S')
  # app_build(window=True, timestamp=current)
