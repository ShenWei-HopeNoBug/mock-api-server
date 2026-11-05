# -*- coding: utf-8 -*-
import json
import math
import os
import re
import shutil
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import requests
from requests.exceptions import ConnectionError

from app_types.download_types import DownloadProxyItem
from config.default import DEFAULT_AUTO_ADJUST_DOWNLOAD_TIMEOUT, DEFAULT_DOWNLOAD_CONNECT_TIMEOUT
from config.enum import DOWNLOAD
from config.work_file import (
  DOWNLOAD_CONFIG_PATH,
  DOWNLOAD_DIR,
  STATIC_DIR,
)
from lib.app_lib import get_mock_api_data_list
from lib.db import MockDBCache
from lib.decorate import error_catch
from lib.logger_lib import DOWNLOAD_LOGGER
from lib.utils_lib import (
  JsonFormat,
  check_and_create_dir,
  compress_image,
  create_md5,
  create_timestamp,
  get_url_domain,
  is_url_match,
  limit_num_range,
)


@error_catch(error_msg='获取导出下载地址列表失败', error_return=[])
def get_output_data_list(log_path: str, work_dir: str = '.') -> List[Dict[str, str]]:
  # 检查下载日志路径
  if not os.path.exists(log_path):
    return []

  static_dir = f'{work_dir}{STATIC_DIR}'
  # 检查静态资源目录
  if not os.path.exists(static_dir):
    return []

  with open(log_path, 'r', encoding='utf-8') as fl:
    logs = json.loads(fl.read())

  path_list = []
  for log in logs:
    success = log.get('success', False)
    file_name = log.get('file_name', '')
    static_path = os.path.abspath(f'{static_dir}/{file_name}')

    # 下载成功且静态资源目录有这个文件，添加到导出列表中
    if success and os.path.exists(static_path):
      path_list.append({
        "path": static_path,
        "file_name": file_name,
      })

  return path_list


@error_catch(error_msg='导出静态资源失败', error_return=[])
def output_static_files(output_dir: str = './output', output_list: Optional[List[Dict[str, str]]] = None) -> None:
  if output_list is None:
    output_list = []

  if not len(output_list):
    return

  # 拼接导出文件夹路径
  save_dir = os.path.abspath(f'{output_dir}/output-static-{create_timestamp()}')

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



# 获取静态资源匹配正则对象
def get_static_match_regexp(include_files: List[str]) -> re.Pattern:
  if not isinstance(include_files, list):
    include_files = []
  pattern = r'(https?://[-/a-zA-Z0-9_.!]*(?:{}))'.format('|'.join(include_files))
  return re.compile(pattern, flags=re.IGNORECASE)


# 写入下载日志
@error_catch(error_msg='写入下载日志失败')
def write_download_log(
    work_dir: str = '.',
    download_log: Optional[List[Dict[str, Any]]] = None,
    log_name: str = 'log'
) -> None:
  if not isinstance(download_log, list):
    download_log = []

  # 没有内容不写入
  if not len(download_log):
    return

  # 下载日志路径
  download_log_path = f'{work_dir}{DOWNLOAD_DIR}/{log_name}.json'

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

  def update_detail(self, url: str = '', connect_error: bool = False) -> None:
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

  def get_timeout(self, url: str = '') -> int:
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

  def __compute_timeout(self, connect_error_count: int = 0) -> int:
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


# 静态资源下载器（一次实例对应一次完整下载运行，运行级状态收敛于实例属性）
class StaticAssetDownloader:
  def __init__(
      self,
      work_dir: str = '.',
      static_url_path: str = STATIC_DIR,
      compress: bool = True,
      callback: Optional[Callable[[Dict[str, Any]], None]] = None,
      stop_event: Optional[threading.Event] = None,
      session: Optional[Any] = None,
  ):
    self.work_dir = work_dir
    # 静态资源目录
    self.assets_dir = f'{work_dir}{static_url_path}'
    self.compress = compress
    self.callback = callback
    self.stop_event = stop_event
    # 会话注入点：默认 requests 模块（无 cookie jar，与裸 requests.get 等价），测试可注入 mock
    self.session = session or requests

    # 运行级状态（run() 开头装载）
    self.config: dict = {}
    self.base_timeout = DEFAULT_DOWNLOAD_CONNECT_TIMEOUT
    self.auto_adjust_timeout = DEFAULT_AUTO_ADJUST_DOWNLOAD_TIMEOUT
    self.download_proxy_list: List[DownloadProxyItem] = []
    self.detail_manager = DownloadDetailManager(timeout=self.base_timeout)
    self.download_log: list = []
    self.log_name = ''

  # 执行一次完整下载运行
  def run(self) -> None:
    """一次完整的静态资源下载运行。

    核心流程：
      1. _load_config 读取下载配置（include_files / 超时 / 代理），
         并初始化动态超时管理器、下载日志容器；
      2. _get_ready_assets 扫描 mock 数据与静态资源表提取 URL，
         剔除本地已下载文件，得到待下载列表；
      3. 逐条调用 _download_one 下载，每轮结束 _write_log 增量落盘。

    运行机制：
      - 超时：auto_adjust_timeout 开启时按域名连续连接失败次数
        动态收缩超时（DownloadDetailManager），快速跳过不可达资源；
      - 代理：每个 URL 按 download_proxy_list 的 includes 规则
        独立匹配代理（_get_proxies）；
      - 落盘：先写 .part 再 os.replace 原子改名，中断不留残缺文件；
      - 日志：download_log 内存累积，每条资源处理完即写入
        download/<log_name>.json；success 字段供导出功能过滤；
      - 中断：stop_event 命中立即返回，不写日志不打「完毕」；
      - 进度：每条下载前回调 callback(current/total/asset)。
    """
    DOWNLOAD_LOGGER.info('>' * 10 + ' 开始检查和下载静态资源...')

    # 装载运行级状态
    self.config = self._load_config()
    # 基准下载超时时间
    self.base_timeout = self.config.get('download_timeout', DEFAULT_DOWNLOAD_CONNECT_TIMEOUT)
    # 是否动态调整下载超时连接时间
    self.auto_adjust_timeout = self.config.get(
      'auto_adjust_timeout',
      DEFAULT_AUTO_ADJUST_DOWNLOAD_TIMEOUT,
    )
    # 下载代理配置列表
    self.download_proxy_list = self.config.get('download_proxy_list', [])
    # 下载详情管理器
    self.detail_manager = DownloadDetailManager(timeout=self.base_timeout)
    # 下载日志
    self.download_log = []
    self.log_name = create_timestamp()

    # 待下载静态资源列表
    download_assets = self._get_ready_assets()

    # 静态资源列表为空
    if not len(download_assets):
      DOWNLOAD_LOGGER.info('没有需要下载的静态资源！')
      return

    assets_length = len(download_assets)
    for i, asset in enumerate(download_assets):
      # 检查是否退出下载
      if self.stop_event is not None and self.stop_event.is_set():
        return
      self._download_one(asset, i, assets_length)

    DOWNLOAD_LOGGER.info('下载静态资源完毕！')

  # 读取下载配置
  @error_catch(error_msg='获取下载配置失败', error_return={})
  def _load_config(self) -> dict:
    download_config_path = f'{self.work_dir}{DOWNLOAD_CONFIG_PATH}'
    if not os.path.exists(download_config_path):
      return {}

    with open(download_config_path, 'r', encoding='utf-8') as fl:
      download_config = json.loads(fl.read())

    return download_config

  # 获取待下载静态资源列表（经过本地已下载校验后剔除了已下载的静态资源）
  @error_catch(error_msg='获取待下载静态资源列表失败', error_return=[])
  def _get_ready_assets(self) -> List[str]:
    # 获取下载静态资源列表
    assets_list = self._get_assets_list()

    # 创建静态资源文件夹
    check_and_create_dir(self.assets_dir)

    download_assets = []
    # 检查需要下载的静态资源文件
    for asset in assets_list:
      # 检查是否退出下载
      if self.stop_event is not None and self.stop_event.is_set():
        return []

      file_name = asset.split('/')[-1]

      # 拼接图片存放地址和名字
      assets_path = f'{self.assets_dir}/{file_name}'
      # 只添加本地没下载过的静态资源
      if not os.path.exists(assets_path):
        download_assets.append(asset)

    return download_assets

  # 获取下载静态资源列表（包含所有的静态资源，没进行本地已下载校验）
  @error_catch(error_msg='获取下载静态资源列表失败', error_return=[])
  def _get_assets_list(self) -> List[str]:
    include_files = self.config.get('include_files', [])
    download_include_files = list(set(include_files))

    # 没有配置要下载的文件类型，直接退出
    if not len(download_include_files):
      return []

    # mock 数据列表（包括抓包数据和自定义数据）
    mock_api_data_list = get_mock_api_data_list(work_dir=self.work_dir)
    # 抓取的静态资源数据
    mock_db = MockDBCache.get(self.work_dir)
    static_data_list = mock_db.get_static_list()

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
      assets = assets_reg.findall(url)
      assets_list.extend(assets)

    # 去重
    return list(set(assets_list))

  # 获取下载代理配置
  @error_catch(error_msg='获取下载代理配置失败', error_return={})
  def _get_proxies(self, url: str) -> Dict[str, str]:
    if not url or not isinstance(self.download_proxy_list, list):
      return {}

    proxies = {}
    for conf in self.download_proxy_list:
      protocol = conf.get('protocol', '')
      proxy = conf.get('proxy', '')
      includes = conf.get('includes', [])
      includes = list(set(includes))
      # 根据匹配情况设置代理
      if is_url_match(url=url, includes=includes):
        proxies[protocol] = proxy

    return proxies

  # 下载单个静态资源
  def _download_one(self, asset: str, i: int, total: int) -> None:
    file_name = asset.split('/')[-1]

    # 保存图片的地址
    assets_path = os.path.abspath(f'{self.assets_dir}/{file_name}')
    # 下载临时文件路径（先写 .part 再原子改名，中断不留残缺文件）
    part_path = f'{assets_path}.part'

    # 校验下载的文件是否已经存在
    if os.path.exists(assets_path):
      return

    # 调用回调
    if callable(self.callback):
      self.callback({
        "current": i + 1,
        "total": total,
        "asset": asset,
      })

    connect_timeout = self.detail_manager.get_timeout(url=asset) if self.auto_adjust_timeout else self.base_timeout
    proxies = self._get_proxies(url=asset)
    DOWNLOAD_LOGGER.info(
      f'\n******** 正在下载：{i + 1}/{total} ********\nCONNECT_TIMEOUT：{connect_timeout}s\nURL：{asset}\nPROXIES：{proxies}'
    )

    # 日志条目静态字段（各分支共用，仅 success/message 为差异点）
    log_base = {
      "url": asset,
      "save_path": assets_path,
      "file_name": file_name,
      "proxies": proxies,
    }

    # 下载静态资源
    try:
      response = self.session.get(asset, timeout=(connect_timeout, DOWNLOAD.READ_TIMEOUT), proxies=proxies)
      if response.status_code != 200:
        DOWNLOAD_LOGGER.warning(f'下载失败：{asset}')
        # 保存下载日志
        self._append_log(log_base, False, f"下载失败! STATUS_CODE:{response.status_code}")
        self._write_log()
        return

      # 更新下载详情
      if self.auto_adjust_timeout:
        self.detail_manager.update_detail(url=asset, connect_error=False)

      # 将文件写入指定位置
      assets_data = response.content
      with open(part_path, 'wb') as fl:
        fl.write(assets_data)
      os.replace(part_path, assets_path)

      # 压缩下载图片（压缩失败不影响文件可用性，仅记 warning）
      if self.compress:
        try:
          compress_image(
            input_path=assets_path,
            output_path=assets_path,
            quality=80
          )
        except Exception as e:
          DOWNLOAD_LOGGER.warning(f'压缩图片失败，保留原图：{file_name} {e}')

      # 保存下载日志
      self._append_log(log_base, True)

      time.sleep(0.8)
    except ConnectionError as e:
      DOWNLOAD_LOGGER.warning(f'下载静态资源连接异常！{e}')
      # 更新下载详情
      if self.auto_adjust_timeout:
        self.detail_manager.update_detail(url=asset, connect_error=True)
      # 清理可能残留的临时文件
      if os.path.exists(part_path):
        os.remove(part_path)
      # 保存下载日志
      self._append_log(log_base, False, f"下载连接异常! ConnectionError:{e}")
    except Exception as e:
      DOWNLOAD_LOGGER.warning(f'下载静态资源出错！{e}')
      # 清理可能残留的临时文件
      if os.path.exists(part_path):
        os.remove(part_path)
      # 保存下载日志
      self._append_log(log_base, False, f"下载报错! ERROR:{e}")
    finally:
      DOWNLOAD_LOGGER.info('*' * 29)

    self._write_log()

  # 追加下载日志条目
  def _append_log(self, log_base: Dict[str, Any], success: bool, message: str = '') -> None:
    self.download_log.append({**log_base, "success": success, "message": message})

  # 写入下载日志
  def _write_log(self) -> None:
    write_download_log(
      work_dir=self.work_dir,
      download_log=self.download_log,
      log_name=self.log_name,
    )


# 下载mock服务需要静态资源
@error_catch(error_msg='下载 Mock Server 静态资源失败')
def download_server_static(
    work_dir: str = '.',
    static_url_path: str = STATIC_DIR,
    compress: bool = True,
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    stop_event: Optional[threading.Event] = None,
) -> None:
  StaticAssetDownloader(
    work_dir=work_dir,
    static_url_path=static_url_path,
    compress=compress,
    callback=callback,
    stop_event=stop_event,
  ).run()
