# -*- coding: utf-8 -*-
import subprocess
import global_var
import os
import shutil
import datetime


def create_timestamp():
  return datetime.datetime.now().strftime('%Y%m%d%H%M%S')


'''
打包应用
@:param window -打包的应用是否带黑窗
@:param timestamp -打包应用名带的时间戳
'''
def app_build(window=False, timestamp=''):
  # 当前版本号
  version = global_var.version
  win_ext = '.win' if window else ''
  time_ext = '.{}'.format(timestamp) if timestamp else ''
  app_name = 'mockServer{}{}-{}'.format(win_ext, time_ext, version)
  args = ["pyinstaller", f"--name={app_name}", "main.py", "-F"]
  # 打包命令加上黑窗
  if not window:
    args.append("-w")
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


if __name__ == '__main__':
  current = create_timestamp()
  app_build(window=False, timestamp=current)
  app_build(window=True, timestamp=current)
