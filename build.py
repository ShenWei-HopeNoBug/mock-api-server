# -*- coding: utf-8 -*-
import subprocess
from config import globals
import os
import re
import shutil
from lib.utils_lib import create_timestamp

# 构建配置模块文件（打包时动态生成，编译进每个 exe 的 PYZ 中）
# 相比 JSON + --add-data 方案，Python 模块方式将配置编译进 exe 内部，
# 使得多个 exe 可以共用同一份 site-packages 而不会产生配置文件冲突
BUILD_CONFIG_MODULE = './_build_config.py'


def generate_build_config(mitmproxy_log, version):
  """生成构建配置 Python 模块

  打包时会被 PyInstaller 编译进 exe 的 PYZ 字节码中，
  每个 exe 各自持有独立的配置副本，互不干扰。
  """
  content = f'''# -*- coding: utf-8 -*-
# 此文件由 build.py 自动生成，请勿手动编辑
MITMPROXY_LOG = {mitmproxy_log}
VERSION = '{version}'
'''
  with open(BUILD_CONFIG_MODULE, 'w', encoding='utf-8') as f:
    f.write(content)
  print(f'写入构建配置模块：\n{content}')


def _modify_spec_for_exe_only(spec_path, new_name, console):
  """修改 PyInstaller spec 文件，只构建 EXE 跳过 COLLECT

  - 修改 EXE 的 name 和 console 参数
  - 移除 COLLECT 段（不再复制 site-packages，复用第一个包的完整依赖）
  - 保留 content_directory 设置（确保 exe 能在共享目录中找到 site-packages）
  """
  with open(spec_path, 'r', encoding='utf-8') as f:
    content = f.read()

  # 提取 contents_directory 设置（可能在 EXE 或 COLLECT 中）
  cd_match = re.search(r"contents_directory=['\"]([^'\"]*)['\"]", content)
  content_directory = cd_match.group(1) if cd_match else None

  # 移除 COLLECT 段（从 "coll = COLLECT(" 到文件末尾）
  collect_match = re.search(r'\ncoll = COLLECT\(', content)
  if collect_match:
    content = content[:collect_match.start()].rstrip() + '\n'

  # 修改 EXE 的 name 参数
  content = re.sub(r"(name=)'[^']*'", rf"\1'{new_name}'", content, count=1)

  # 修改 EXE 的 console 参数
  content = re.sub(r"console=(True|False)", f"console={console}", content, count=1)

  # 如果 contents_directory 原本只在 COLLECT 中，移除后需要补到 EXE 段
  if content_directory and 'contents_directory=' not in content:
    lines = content.split('\n')
    for i in range(len(lines)):
      # 找到 EXE 块的闭合括号（第一个单独的 ')' 行）
      if lines[i].strip() == ')' and i > 0:
        lines.insert(i, f"    contents_directory='{content_directory}',")
        break
    content = '\n'.join(lines)

  with open(spec_path, 'w', encoding='utf-8') as f:
    f.write(content)
  print(f'修改 spec 文件（仅 EXE，跳过 COLLECT）：{spec_path}')


'''
完整打包：生成 exe + site-packages，保留 spec 文件供第二次构建复用
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
    "main.py",
    "-D",
  ]
  # 打包命令加上黑窗
  if not window:
    args.append("-w")

  # 开始打包
  subprocess.run(args)

  spec_file = f'./{app_name}.spec'
  # 不删除 spec 文件，供第二次构建复用

  # 删除临时的打包文件夹
  build_tmp_dir = './build'
  if os.path.exists(build_tmp_dir):
    shutil.rmtree(build_tmp_dir)
    print(f'删除文件夹：{build_tmp_dir}')

  return {
    "app_name": app_name,
    "version": version,
    "spec_file": spec_file,
  }


'''
仅构建 EXE（复用第一个包的 site-packages），跳过 COLLECT 步骤
@:param spec_file -第一个包生成的 spec 文件路径
@:param window -打包的应用是否带黑窗
@:param timestamp -打包应用名带的时间戳
'''


def exe_only_build(spec_file, window, timestamp=''):
  # 当前版本号
  version = globals.version
  win_ext = '.win' if window else ''
  time_ext = f'.{timestamp}' if timestamp else ''
  # 版本tag
  app_version_tag = f'{version}-{timestamp}' if timestamp else version
  app_name = f'mockServer{win_ext}{time_ext}-{version}'

  # 生成此变体的构建配置（会编译进新 exe 的 PYZ 中）
  generate_build_config(mitmproxy_log=window, version=app_version_tag)

  # 基于 spec 文件构建，修改 name 和 console，跳过 COLLECT
  _modify_spec_for_exe_only(spec_file, app_name, window)

  # 使用修改后的 spec 文件构建（--noconfirm 覆盖已有产物）
  subprocess.run(["pyinstaller", spec_file, "--noconfirm"])

  # 清理 spec 文件
  if os.path.exists(spec_file):
    os.remove(spec_file)
    print(f'删除文件：{spec_file}')

  # 无 COLLECT 时 PyInstaller 不会把 exe 复制到 dist/，
  # exe 只存在于 build/ 目录中，需要手动提取。
  # 注意：PyInstaller 用 spec 文件名（而非 EXE 内的 name 参数）作为 build 子目录名，
  # 而 exe 文件名用的是 EXE 内的 name 参数，两者可能不同。
  spec_stem = os.path.splitext(os.path.basename(spec_file))[0]
  exe_in_build = f'./build/{spec_stem}/{app_name}.exe'
  exe_path = f'./dist/{app_name}.exe'
  if os.path.exists(exe_in_build):
    shutil.move(exe_in_build, exe_path)
    print(f'提取 exe：{exe_in_build} -> {exe_path}')
  else:
    print(f'警告：未找到构建产物 {exe_in_build}')

  # 删除临时构建缓存
  build_tmp_dir = './build'
  if os.path.exists(build_tmp_dir):
    shutil.rmtree(build_tmp_dir)
    print(f'删除文件夹：{build_tmp_dir}')

  return {
    "app_name": app_name,
    "version": version,
    "exe_path": exe_path,
  }


# 批量打包
def batch_build():
  current = create_timestamp('%Y%m%d%H%M%S')

  # 第一个包：完整构建（生成 exe + site-packages + spec 文件）
  # 以不带黑窗的正常版本作为基础包，最终目录以此命名
  build_info = app_build(window=False, timestamp=current)
  build_app_name = build_info.get('app_name')
  spec_file = build_info.get('spec_file')

  # 第二个包：仅构建 EXE，复用第一个包的 site-packages
  # 通过修改 spec 跳过 COLLECT，不重复复制依赖文件
  win_build_info = exe_only_build(spec_file, window=True, timestamp=current)
  win_build_app_name = win_build_info.get('app_name')
  win_exe_path = win_build_info.get('exe_path')

  # 将带黑窗的 exe 移动到不带黑窗的打包目录下（共用 site-packages）
  move_dir = f'./dist/{build_app_name}'

  path_valid = os.path.exists(move_dir) and os.path.exists(win_exe_path)
  print(f'路径检测：\n ---> from：{win_exe_path}  \n ---> to：{move_dir} \n valid：{path_valid}')

  if os.path.exists(move_dir) and os.path.exists(win_exe_path):
    print(f'开始移动打包产物：\n{win_exe_path} -> {move_dir}')
    shutil.move(win_exe_path, move_dir)
  else:
    print('警告：未找到第二个 exe 文件，可能 spec 修改未生效')

  # 清理临时构建配置模块
  if os.path.exists(BUILD_CONFIG_MODULE):
    os.remove(BUILD_CONFIG_MODULE)
    print(f'删除文件：{BUILD_CONFIG_MODULE}')


if __name__ == '__main__':
  # 批量打包
  batch_build()
