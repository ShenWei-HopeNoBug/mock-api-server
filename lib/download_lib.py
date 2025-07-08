# -*- coding: utf-8 -*-
import os
import json
import shutil
import re
import time
import requests
from config.work_file import (
  DOWNLOAD_CONFIG_PATH,
  STATIC_DIR,
  DOWNLOAD_DIR,
)
from lib.decorate import error_catch
from lib.utils_lib import (
  check_and_create_dir,
  create_timestamp,
  JsonFormat,
  compress_image,
)
from lib.app_lib import get_mock_api_data_list
from lib import server_lib
from lib.system_lib import GLOBALS_CONFIG_MANAGER


@error_catch(error_msg='获取导出下载地址列表失败', error_return=[])
def get_output_data_list(log_path: str, work_dir: str = '.'):
  # 检查下载日志路径
  if not os.path.exists(log_path):
    return []

  static_dir = r'{}{}'.format(work_dir, STATIC_DIR)
  # 检查静态资源目录
  if not os.path.exists(static_dir):
    return []

  with open(log_path, 'r', encoding='utf-8') as fl:
    logs = json.loads(fl.read())

  path_list = []
  for log in logs:
    success = log.get('success', False)
    file_name = log.get('file_name', '')
    static_path = os.path.abspath(r'{}/{}'.format(static_dir, file_name))

    # 下载成功且静态资源目录有这个文件，添加到导出列表中
    if success and os.path.exists(static_path):
      path_list.append({
        "path": static_path,
        "file_name": file_name,
      })

  return path_list


@error_catch(error_msg='导出静态资源失败', error_return=[])
def output_static_files(output_dir='./output', output_list=None):
  if output_list is None:
    output_list = []

  if not len(output_list):
    return

  # 拼接导出文件夹路径
  save_dir = os.path.abspath(r'{}/output-static-{}'.format(
    output_dir,
    create_timestamp(),
  ))

  # 检查并创建导出路径
  check_and_create_dir(save_dir)

  # 待导出文件集合
  path_set = set()
  for output_data in output_list:
    path = output_data.get('path')
    file_name = output_data.get('file_name', '')
    if not (path and file_name and os.path.exists(path)):
      continue

    path_set.add(path)

  for path in path_set:
    # 复制静态资源到目标文件夹
    shutil.copy(path, save_dir)


# 是否退出下载
def is_exit_download() -> bool:
  client_exit = GLOBALS_CONFIG_MANAGER.get(key='client_exit')
  download_exit = GLOBALS_CONFIG_MANAGER.get(key='download_exit')
  return client_exit or download_exit


@error_catch(error_msg='获取下载配置失败', error_return={})
def get_download_config(work_dir='.') -> dict:
  download_config_path = r'{}{}'.format(work_dir, DOWNLOAD_CONFIG_PATH)
  if not os.path.exists(download_config_path):
    return {}

  # 读取下载配置
  with open(download_config_path, 'r', encoding='utf-8') as fl:
    download_config = json.loads(fl.read())

  return download_config


# 获取静态资源匹配正则对象
def get_static_match_regexp(include_files: list):
  if type(include_files) != list:
    include_files = []
  pattern = r'(https?://[-/a-zA-Z0-9_.!]*(?:{}))'.format('|'.join(include_files))
  return re.compile(pattern, flags=re.IGNORECASE)


# 获取下载静态资源列表（包含所有的静态资源，没进行本地已下载校验）
@error_catch(error_msg='获取下载静态资源列表失败', error_return=[])
def get_download_assets_list(work_dir='.') -> list:
  # 读取下载配置
  download_config = get_download_config(work_dir=work_dir)
  include_files = download_config.get('include_files', [])
  download_include_files = list(set(include_files))

  # 没有配置要下载的文件类型，直接退出
  if not len(download_include_files):
    return []

  # mock 数据列表（包括抓包数据和自定义数据）
  mock_api_data_list = get_mock_api_data_list(work_dir=work_dir)
  # 抓取的静态资源数据
  static_data_list = server_lib.get_static_data_list(work_dir=work_dir)

  # 静态资源链接列表
  assets_list = []
  # 提取 response 静态资源链接
  assets_reg = get_static_match_regexp(download_include_files)
  for row_data in mock_api_data_list:
    response = row_data.get('response', '')
    assets = assets_reg.findall(response)
    assets_list.extend(assets)

  # 添加静态资源链接
  for row_data in static_data_list:
    url = row_data.get('url', '')
    assets_list.append(url)

  # 去重
  assets_list = list(set(assets_list))

  return assets_list


# 获取待下载静态资源列表（经过本地已下载校验后剔除了已下载的静态资源）
@error_catch(error_msg='获取待下载静态资源列表失败', error_return=[])
def get_download_ready_assets(work_dir='.', static_url_path=STATIC_DIR) -> list:
  # 获取下载静态资源列表
  assets_list = get_download_assets_list(work_dir=work_dir)

  # 静态资源目录
  assets_dir = '{}{}'.format(work_dir, static_url_path)
  # 创建静态资源文件夹
  check_and_create_dir(assets_dir)

  download_assets = []
  # 检查需要下载的静态资源文件
  for asset in assets_list:
    # 检查是否退出下载
    if is_exit_download():
      return []

    file_name = asset.split('/')[-1]

    # 拼接图片存放地址和名字
    assets_path = '{}/{}'.format(assets_dir, file_name)
    # 只添加本地没下载过的静态资源
    if not os.path.exists(assets_path):
      download_assets.append(asset)

  return download_assets


# 写入下载日志
@error_catch(error_msg='写入下载日志失败')
def white_download_log(work_dir='.', download_log=None, log_name='log'):
  if type(download_log) != list:
    download_log = []

  # 没有内容不写入
  if not len(download_log):
    return

  # 下载日志路径
  download_log_path = '{}{}/{}.json'.format(
    work_dir,
    DOWNLOAD_DIR,
    log_name,
  )

  with open(download_log_path, 'w', encoding='utf-8') as fl:
    fl.write(JsonFormat.dumps(download_log))


# 下载mock服务需要静态资源
@error_catch(error_msg='下载 Mock Server 静态资源失败')
def download_server_static(
    work_dir='.',
    static_url_path=STATIC_DIR,
    compress=True,
    callback=None,
):
  print('>' * 10, '开始检查和下载静态资源...')
  # 待下载静态资源列表
  download_assets = get_download_ready_assets(
    work_dir=work_dir,
    static_url_path=static_url_path,
  )

  # 静态资源列表为空
  if not len(download_assets):
    print('没有需要下载的静态资源！')
    return

  # 静态资源目录
  assets_dir = '{}{}'.format(work_dir, static_url_path)

  # 下载日志
  download_log = []
  log_name = create_timestamp()

  # 写入日志
  def white_log():
    white_download_log(
      work_dir=work_dir,
      download_log=download_log,
      log_name=log_name,
    )

  assets_length = len(download_assets)
  for i, asset in enumerate(download_assets):
    # 检查是否退出下载
    if is_exit_download():
      return

    file_name = asset.split('/')[-1]

    # 保存图片的地址
    assets_path = os.path.abspath('{}/{}'.format(assets_dir, file_name))

    # 校验下载的文件是否已经存在
    if os.path.exists(assets_path):
      continue

    print('{}/{} 正在下载：{}'.format(i + 1, assets_length, asset))
    # 调用回调
    if callable(callback):
      callback({
        "current": i + 1,
        "total": assets_length,
        "asset": asset,
      })
    # 下载静态资源
    try:
      response = requests.get(asset, timeout=120)
      if response.status_code != 200:
        print('下载失败：{}'.format(asset))
        # 保存下载日志
        download_log.append({
          "url": asset,
          "save_path": assets_path,
          "file_name": file_name,
          "success": False,
          "message": "下载失败! STATUS_CODE:{}".format(response.status_code),
        })
        white_log()
        continue

      assets_data = response.content

      # 将文件写入指定位置
      with open(assets_path, 'wb') as fl:
        fl.write(assets_data)

      # 压缩下载图片
      if compress:
        compress_image(
          input_path=assets_path,
          output_path=assets_path,
          quality=80
        )

      # 保存下载日志
      download_log.append({
        "url": asset,
        "save_path": assets_path,
        "file_name": file_name,
        "success": True,
        "message": ""
      })

      time.sleep(0.8)
    except Exception as e:
      print('下载静态资源出错！', e)
      # 保存下载日志
      download_log.append({
        "url": asset,
        "save_path": assets_path,
        "file_name": file_name,
        "success": True,
        "message": "下载报错! ERROR:{}".format(e),
      })

    white_log()

  print('下载静态资源完毕！')
