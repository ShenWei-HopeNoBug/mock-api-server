# -*- coding: utf-8 -*-
import os
import json
import shutil
import re
import time
import math
import requests
from requests.exceptions import ConnectionError
from config.work_file import (
  DOWNLOAD_CONFIG_PATH,
  STATIC_DIR,
  DOWNLOAD_DIR,
)
from config.enum import DOWNLOAD
from config.default import (DEFAULT_DOWNLOAD_CONNECT_TIMEOUT, DEFAULT_AUTO_ADJUST_DOWNLOAD_TIMEOUT)
from lib.decorate import error_catch
from lib.utils_lib import (
  check_and_create_dir,
  create_timestamp,
  JsonFormat,
  compress_image,
  get_url_domain,
  create_md5,
  limit_num_range,
  is_url_match,
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


class DownloadDetailManager:
  def __init__(self, timeout: int = DEFAULT_DOWNLOAD_CONNECT_TIMEOUT):
    # 基准下载超时时间
    self.timeout: int = limit_num_range(
      num=timeout,
      min_limit=DOWNLOAD.MIN_CONNECT_TIMEOUT,
      max_limit=DOWNLOAD.MAX_CONNECT_TIMEOUT,
    )

    # 下载详情
    self.detail: dict = {}

  def update_detail(self, url: str = '', connect_error: bool = False):
    domain = get_url_domain(url)
    if not domain:
      return

    search_key = create_md5(domain)

    if search_key not in self.detail:
      add_connect_error_count = 1 if connect_error else 0
      self.detail[search_key] = {
        "domain": domain,
        "connect_error_count": add_connect_error_count,
        "timeout": self.__compute_timeout(connect_error_count=add_connect_error_count),
      }
      return

    domain_detail: dict = self.detail.get(search_key, {})
    connect_error_count = domain_detail.get('connect_error_count', 0)
    # 如果这次没超时，清空连续超时次数
    connect_error_count = 0 if not connect_error else (connect_error_count + 1)

    domain_detail['connect_error_count'] = connect_error_count
    domain_detail['timeout'] = self.__compute_timeout(connect_error_count=connect_error_count)
    self.detail[search_key] = domain_detail

  def get_timeout(self, url: str = ''):
    @error_catch(error_msg='获取连接超时时间失败', error_return=self.timeout)
    def callback():
      domain = get_url_domain(url)
      if not domain:
        return self.timeout

      # 没查到记录，返回配置值
      search_key = create_md5(domain)
      if search_key not in self.detail:
        return self.timeout

      # 返回记录的超时值
      domain_detail: dict = self.detail.get(search_key, {})
      return domain_detail.get('timeout', self.timeout)

    return callback()

  def __compute_timeout(self, connect_error_count: int = 0):
    # 超出连接失败最大次数，直接把超时时间设置为超小值，方便过无法下载的资源
    if connect_error_count >= DOWNLOAD.CONNECT_ERROR_MAX_LIMIT:
      return 1

    # 超出连接失败限制次数，直接把超时时间设置成最小值
    if connect_error_count >= DOWNLOAD.CONNECT_ERROR_LIMIT:
      return DOWNLOAD.MIN_CONNECT_TIMEOUT

    # 当前配置超时时间小于动态调整最小超时时间，直接取配置的超时时间
    if self.timeout <= DOWNLOAD.DYNAMIC_MIN_CONNECT_TIMEOUT:
      return self.timeout

    count: int = 0
    timeout: int = self.timeout
    # 每链接失败一次超时时间就变为原来的一半
    while count < connect_error_count:
      timeout = math.floor(timeout / 2)
      count += 1

    return limit_num_range(
      num=timeout,
      min_limit=DOWNLOAD.DYNAMIC_MIN_CONNECT_TIMEOUT,
      max_limit=DOWNLOAD.MAX_CONNECT_TIMEOUT,
    )


# 获取下载代理配置
def get_download_proxies(url: str, download_proxy_list: list) -> dict:
  if not url or type(download_proxy_list) != list:
    return {}

  proxies = {}
  for conf in download_proxy_list:
    protocol = conf.get('protocol', '')
    proxy = conf.get('proxy', '')
    includes = conf.get('includes', [])
    includes = list(set(includes))
    # 根据匹配情况设置代理
    if is_url_match(url=url, includes=includes):
      proxies[protocol] = proxy

  return proxies


# 下载mock服务需要静态资源
@error_catch(error_msg='下载 Mock Server 静态资源失败')
def download_server_static(
    work_dir: str = '.',
    static_url_path: str = STATIC_DIR,
    compress: bool = True,
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
  download_log: list = []
  log_name = create_timestamp()

  # 写入日志
  def white_log():
    white_download_log(
      work_dir=work_dir,
      download_log=download_log,
      log_name=log_name,
    )

  assets_length = len(download_assets)

  download_config = get_download_config(work_dir=work_dir)
  # 基准下载超时时间
  base_timeout = download_config.get('download_timeout', DEFAULT_DOWNLOAD_CONNECT_TIMEOUT)
  # 是否动态调整下载超时连接时间
  auto_adjust_timeout = download_config.get(
    'auto_adjust_timeout',
    DEFAULT_AUTO_ADJUST_DOWNLOAD_TIMEOUT,
  )
  # 下载代理配置列表
  download_proxy_list = download_config.get('download_proxy_list', [])

  # 下载详情管理器
  download_detail_manager = DownloadDetailManager(timeout=base_timeout)

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

    # 调用回调
    if callable(callback):
      callback({
        "current": i + 1,
        "total": assets_length,
        "asset": asset,
      })

    connect_timeout = download_detail_manager.get_timeout(url=asset) if auto_adjust_timeout else base_timeout
    proxies = get_download_proxies(url=asset, download_proxy_list=download_proxy_list)
    print('\n******** 正在下载：{}/{} ********\nCONNECT_TIMEOUT：{}s\nURL：{}\nPROXIES：{}'.format(
      i + 1,
      assets_length,
      connect_timeout,
      asset,
      proxies,
    ))
    # 下载静态资源
    try:
      response = requests.get(asset, timeout=(connect_timeout, DOWNLOAD.READ_TIMEOUT), proxies=proxies)
      if response.status_code != 200:
        print('下载失败：{}'.format(asset))
        # 保存下载日志
        download_log.append({
          "url": asset,
          "save_path": assets_path,
          "file_name": file_name,
          "proxies": proxies,
          "success": False,
          "message": "下载失败! STATUS_CODE:{}".format(response.status_code),
        })
        white_log()
        continue

      # 更新下载详情
      if auto_adjust_timeout:
        download_detail_manager.update_detail(url=asset, connect_error=False)

      # 将文件写入指定位置
      assets_data = response.content
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
        "proxies": proxies,
        "success": True,
        "message": ""
      })

      time.sleep(0.8)
    except ConnectionError as e:
      print('下载静态资源连接异常！', e)
      # 更新下载详情
      if auto_adjust_timeout:
        download_detail_manager.update_detail(url=asset, connect_error=True)
      # 保存下载日志
      download_log.append({
        "url": asset,
        "save_path": assets_path,
        "file_name": file_name,
        "proxies": proxies,
        "success": True,
        "message": "下载连接异常! ConnectionError:{}".format(e),
      })
    except Exception as e:
      print('下载静态资源出错！', e)
      # 保存下载日志
      download_log.append({
        "url": asset,
        "save_path": assets_path,
        "file_name": file_name,
        "proxies": proxies,
        "success": True,
        "message": "下载报错! ERROR:{}".format(e),
      })
    finally:
      print('*' * 29)

    white_log()

  print('下载静态资源完毕！')
