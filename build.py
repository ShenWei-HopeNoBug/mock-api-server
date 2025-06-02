# -*- coding: utf-8 -*-
import subprocess
from config import globals
import os
import shutil
from lib.utils_lib import create_timestamp


# 设置环境变量
def set_env_params(mitmproxy_log=False):
  with open('./ENV.py', 'w', encoding='utf-8') as fl:
    data = 'mitmproxy_log = {}\n'.format(mitmproxy_log)
    print('写入环境变量：', data)
    fl.write(data)


'''
打包应用
@:param window -打包的应用是否带黑窗
@:param timestamp -打包应用名带的时间戳
'''


def app_build(window=False, timestamp=''):
  # 当前版本号
  version = globals.version
  win_ext = '.win' if window else ''
  time_ext = '.{}'.format(timestamp) if timestamp else ''
  app_name = 'mockServer{}{}-{}'.format(win_ext, time_ext, version)
  args = [
    "pyinstaller",
    f"--name={app_name}",
    f"--contents-directory=site-packages",
    "main.py",
    "-D",
  ]
  # 打包命令加上黑窗
  if not window:
    args.append("-w")

  # 设置下环境变量
  set_env_params(mitmproxy_log=window)

  # 开始打包
  subprocess.run(args)

  spec_file = './{}.spec'.format(app_name)
  if os.path.exists(spec_file):
    os.remove(spec_file)
    print('删除文件：{}'.format(spec_file))

  # 删除临时的打包文件夹
  build_tmp_dir = './build'
  if os.path.exists(build_tmp_dir):
    shutil.rmtree(build_tmp_dir)
    print('删除文件夹：{}'.format(build_tmp_dir))

  # 恢复到默认状态
  set_env_params(mitmproxy_log=True)

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
  win_build_app_dir = './dist/{}'.format(win_build_app_name)
  win_build_app_path = '{}/{}.exe'.format(win_build_app_dir, win_build_app_name)
  move_dir = './dist/{}'.format(build_app_name)

  path_valid = os.path.exists(move_dir) and os.path.exists(win_build_app_path)
  print('路径检测：\n ---> from：{}  \n ---> to：{} \n valid：{}'.format(
    win_build_app_path,
    move_dir,
    path_valid,
  ))

  if os.path.exists(move_dir) and os.path.exists(win_build_app_path):
    print('开始移动打包产物：\n{} -> {}'.format(win_build_app_path, move_dir))
    shutil.move(win_build_app_path, move_dir)
    print('删除文件夹：{}'.format(win_build_app_dir))
    shutil.rmtree(win_build_app_dir)


if __name__ == '__main__':
  # 批量打包
  batch_build()
  # 调试打包
  # app_build(window=True)
