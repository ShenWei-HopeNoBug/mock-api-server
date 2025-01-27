# -*- coding: utf-8 -*-
import subprocess
import global_var
import os
import shutil

'''
打包应用
@:param window -打包的应用是否带黑窗
'''
def app_build(window=False):
  # 当前版本号
  version = global_var.version
  win_ext = '.win' if window else ''
  app_name = 'mockServer{}-{}'.format(win_ext, version)
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
  app_build(window=False)
  app_build(window=True)
