# -*- coding: utf-8 -*-
import os
import webbrowser
from pathlib import Path

from PyQt5.QtWidgets import QMenu, QAction, QApplication
from PyQt5.QtCore import QSharedMemory
from lib.db_lib import MockDB
from config.work_file import DB_DATA_PATH
from lib.decorate import error_catch
from lib.utils_lib import (
  JsonFormat,
  find_process,
  create_md5,
  is_local_server_running,
)
from lib.logger_lib import APP_LOGGER
import psutil
import win32gui
import win32process
import win32con

# 模块级懒加载单例缓存，以 work_dir 绝对路径为 key
_mock_db_cache: dict = {}


def _get_mock_db(work_dir: str = '.') -> MockDB:
  cache_key = os.path.abspath(work_dir)
  if cache_key not in _mock_db_cache:
    db_path = f'{work_dir}{DB_DATA_PATH}'
    _mock_db_cache[cache_key] = MockDB(db_path)
  return _mock_db_cache[cache_key]


def _close_mock_db(work_dir='.'):
  cache_key = os.path.abspath(work_dir)
  mock_db = _mock_db_cache.pop(cache_key, None)
  if mock_db:
    mock_db.close()


def close_all_mock_db():
  for mock_db in _mock_db_cache.values():
    mock_db.close()
  _mock_db_cache.clear()


@error_catch(error_msg='检查应用是否已经在运行异常', error_return=False)
def is_app_running(app_name="APP") -> bool:
  """检查应用是否已经在运行"""
  # 创建共享内存
  shared_memory = QSharedMemory(app_name)

  # 尝试附加到现有共享内存
  if shared_memory.attach():
    return True

  # 创建共享内存段
  if not shared_memory.create(1):
    return True

  # 保存共享内存对象，防止被垃圾回收
  if not hasattr(is_app_running, 'shared_memory'):
    is_app_running.shared_memory = shared_memory
  else:
    shared_memory.deleteLater()

  return False


@error_catch(error_msg='获取共享内存名异常', error_return='APP')
def get_memory_name() -> str:
  app_proc_pid = QApplication.applicationPid()
  app_proc = find_process(app_proc_pid)
  if not app_proc:
    return 'APP'

  app_name = app_proc.name().replace('.win', '')
  memory_name = os.path.abspath(Path(app_name))

  return create_md5(memory_name)


@error_catch(error_msg='查找正在运行的APP实例的进程pid异常', error_return=None)
def find_running_app_pid():
  """查找正在运行的APP实例的进程pid"""
  app_proc_pid = QApplication.applicationPid()
  app_proc = find_process(app_proc_pid)
  if not app_proc:
    APP_LOGGER.info('@@find_running_app_pid 未找到当前运行进程对象')
    return None

  app_proc_name = app_proc.name()
  APP_LOGGER.info(
    f'@@find_running_app_pid 当前运行进程对象信息 pid: {app_proc_pid}  name: {app_proc_name}'
  )

  # 用于匹配的进程名去除.win
  match_proc_name = app_proc_name.replace('.win', '')
  for proc in psutil.process_iter(['pid', 'name']):
    try:
      name = proc.info['name'] or ''
      pid = proc.info['pid']
      # 确保不是当前进程，进程名相同
      if match_proc_name == name.replace('.win', '') and pid != app_proc_pid:
        APP_LOGGER.info(
          f'@@find_running_app_pid 找到的同名运行进程信息 pid: {proc.info["pid"]}  name: {proc.info["name"]}'
        )
        return proc.info['pid']
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
      pass
  APP_LOGGER.info('@@find_running_app_pid 未找到的同名运行进程')
  return None


@error_catch(error_msg='将指定进程的窗口置顶异常')
def bring_to_front(pid):
  """将指定进程的窗口置顶"""
  hwnds = get_process_windows(pid)
  for hwnd in hwnds:
    # 如果窗口最小化，先恢复
    if win32gui.IsIconic(hwnd):
      win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    # 置顶窗口
    win32gui.SetForegroundWindow(hwnd)
    # 确保窗口显示在最前
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)


#  检查app运行文件路径是否合法（不包含中文字符）
def is_app_work_dir_valid():
  app_work_dir = os.path.abspath(Path())
  if not os.path.exists(app_work_dir):
    return False

  # 检查路径中是否包含中文字符
  for char in app_work_dir:
    if '\u4e00' <= char <= '\u9fff':
      return False

  return True


def get_process_windows(pid):
  """获取指定进程ID的所有窗口句柄"""

  def callback(hwnd, hwnds):
    if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
      _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
      if found_pid == pid:
        hwnds.append(hwnd)
    return True

  hwnds = []
  win32gui.EnumWindows(callback, hwnds)
  return hwnds


@error_catch(error_msg='读取 mitmproxy api 数据失败', error_return=[])
def get_mitmproxy_api_data_list(work_dir='.', reverse=False):
  mock_db: MockDB = _get_mock_db(work_dir)
  return mock_db.get_api_list(api_type='MITMPROXY', reverse=reverse)


@error_catch(error_msg='读取 user api 数据失败', error_return=[])
def get_user_api_data_list(work_dir='.', reverse=False):
  mock_db: MockDB = _get_mock_db(work_dir)
  return mock_db.get_api_list(api_type='USER', reverse=reverse)


@error_catch(error_msg='更新 user api 数据失败', error_return=False)
def update_user_api_data(work_dir='.', update_data=None) -> bool:
  # 入参校验
  if type(update_data) != dict:
    return False

  update_id = update_data.get('id', '')
  if not update_id:
    return False

  mock_db: MockDB = _get_mock_db(work_dir)
  return mock_db.update_api(update_data)


@error_catch(error_msg='新增 user api 数据失败', error_return=False)
def add_user_api_data(work_dir='.', add_data=None) -> bool:
  if type(add_data) != dict:
    return False

  record = {
    "type": add_data.get('type', 'USER'),
    "url": add_data.get('url', ''),
    "method": add_data.get('method', 'GET'),
    "params": add_data.get('params', JsonFormat.dumps({})),
    "response": add_data.get('response', JsonFormat.dumps({})),
  }
  mock_db: MockDB = _get_mock_db(work_dir)
  mock_db.upsert_api(record)
  return True


@error_catch(error_msg='删除 user api 数据失败', error_return=False)
def delete_user_api_data(work_dir='.', delete_id: str = '') -> bool:
  if type(delete_id) != str or not delete_id:
    return False

  mock_db: MockDB = _get_mock_db(work_dir)
  return mock_db.delete_api(delete_id)


@error_catch(error_msg='读取 api 数据文件失败', error_return=[])
def get_mock_api_data_list(work_dir='.'):
  mock_db: MockDB = _get_mock_db(work_dir)
  api_list = mock_db.get_api_list(api_type='MITMPROXY')
  api_list.extend(mock_db.get_api_list(api_type='USER'))

  return api_list


# 加工并打开抓包数据预览html
@error_catch(error_msg='打开抓包数据预览html失败', error_return=False)
def open_mitmproxy_preview_html(root_dir='.', work_dir='.'):
  # 预览数据列表
  preview_list = get_mock_api_data_list(work_dir=work_dir)
  base_path = f"{root_dir}/appServer/static/web"

  # 把预览数据写入web的静态资源文件
  web_mitmproxy_output_file = f'{base_path}/mitmproxy_output.js'
  if not os.path.exists(web_mitmproxy_output_file):
    return False
  with open(web_mitmproxy_output_file, 'w', encoding='utf-8') as fl:
    content = f"window.MITMPROXY_OUTPUT = {JsonFormat.dumps(preview_list)};\n"
    fl.write(content)

  preview_html = f'{base_path}/apps/dataPreview/index.html'
  if not os.path.exists(preview_html):
    return False
  # 用浏览器打开预览 html 文件
  webbrowser.open(os.path.abspath(preview_html))

  return True


# 打开操作手册
@error_catch(error_msg='打开操作手册html失败', error_return=False)
def open_operation_manual_html(root_dir='.'):
  base_path = f"{root_dir}/appServer/static/web"
  operation_manual_html = f"{base_path}/apps/document/index.html"
  if not os.path.exists(operation_manual_html):
    return False
  webbrowser.open(os.path.abspath(operation_manual_html))
  return True


# 修复异常的抓包数据（SQLite schema 已保证数据完整性，改为 no-op）
@error_catch(error_msg='修复异常抓包数据失败', error_return=False)
def fix_user_api_data(work_dir='.') -> bool:
  return True


@error_catch(error_msg='批量设置菜单元素配置失败')
def set_menu_config(menu: QMenu, config_list: list):
  def menu_action_callback(action: QAction):
    action_name = action.text()
    for conf in config_list:
      callback = conf.get('callback')
      name = conf.get('name', '')
      if name == action_name:
        if callable(callback):
          callback()
        return

  for config in config_list:
    menu_name = config.get('name', '')
    menu.addAction(menu_name)

  menu.triggered[QAction].connect(menu_action_callback)


# 批量设置菜单元素禁用状态
@error_catch(error_msg='批量设置菜单元素禁用状态失败')
def set_menu_item_disabled(menu: QMenu, disable_list: list):
  if not menu or not len(disable_list):
    return

  # 构造菜单元素禁用状态字典
  disable_dict: dict = {}
  action_set = set()
  for config in disable_list:
    action_name = config.get('action_name', '')
    disabled = config.get('disabled', False)
    if action_name:
      action_set.add(action_name)
      disable_dict[action_name] = disabled

  actions = menu.actions()
  for action in actions:
    if not len(action_set):
      return

    action_name = action.text()
    # 设置匹配到的菜单的禁用状态
    if action_name in action_set:
      disabled = disable_dict.get(action_name, False)
      action.setEnabled(not disabled)
      action_set.remove(action_name)


@error_catch(error_msg='检查 APP_SERVER 是否运行失败！', error_return=False)
def is_app_server_running(app_sever_running_data: dict) -> bool:
  if type(app_sever_running_data) != dict:
    return False

  success = app_sever_running_data.get('success', False)
  port = app_sever_running_data.get('port', 5050)
  if not success:
    return False

  if is_local_server_running(port=port, retry=0, retry_condition='NOT_RUNNING'):
    print(f"检测到 APP_SERVER 运行中！port={port}")
    return True
  else:
    APP_LOGGER.error(f"检测到 APP_SERVER 未运行！port={port}")
    return False
