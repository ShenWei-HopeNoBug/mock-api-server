# -*- coding: utf-8 -*-
import os
import time
import threading
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtWidgets import QMenu, QAction, QApplication
from PyQt5.QtCore import QSharedMemory
from lib.db_lib import MockDB, MockDBCache
from lib.decorate import error_catch
from lib.utils_lib import (
  JsonFormat,
  find_process,
  create_md5,
  is_local_server_running,
)
from app_types.app_gui_types import AppServerRunningData
from app_types.db_types import ApiData, ApiRecord, ApiQuery
from lib.logger_lib import APP_LOGGER
import psutil
import win32gui
import win32process
import win32con


def run_blocking_with_events(app: QApplication, func: Callable, *args: Any, **kwargs: Any) -> Any:
  """在子线程中执行阻塞函数，主线程持续处理事件以保持 UI 响应"""
  # 使用列表存储子线程返回值，避免闭包中 nonlocal 声明
  result: list = [None]
  # 线程事件对象，用于标识子线程是否执行完毕
  done = threading.Event()

  def wrapper() -> None:
    # 在子线程中执行传入的阻塞函数，将返回值存入 result 列表
    result[0] = func(*args, **kwargs)
    # 标记子线程任务完成，通知主线程退出等待循环
    done.set()

  # 创建守护线程，确保主进程退出时子线程不会阻塞
  t = threading.Thread(target=wrapper, daemon=True)
  t.start()

  # 主线程轮询等待子线程完成，期间持续处理 Qt 事件以保持 UI 响应
  while not done.is_set():
    # 处理 Qt 事件队列，保证启动动画等 UI 组件正常刷新
    app.processEvents()
    # 短暂休眠避免主线程空转占用过多 CPU 资源（约 50fps）
    time.sleep(0.02)

  # 返回子线程中阻塞函数的执行结果
  return result[0]


@error_catch(error_msg='检查应用是否已经在运行异常', error_return=True)
def is_app_running(app_name: str = "APP") -> bool:
  """检查应用是否已经在运行"""
  # 创建共享内存
  shared_memory = QSharedMemory(app_name)

  # 尝试附加到现有共享内存
  if shared_memory.attach():
    return True

  # 创建共享内存段
  if not shared_memory.create(1):
    return True

  # 将共享内存对象挂到函数属性上持有引用，防止函数返回后局部变量被垃圾回收导致共享内存段释放
  is_app_running.shared_memory = shared_memory

  return False


def normalize_exe_path(exe_path: str) -> str:
  """归一化 exe 路径：只对文件名部分去除 .win 后缀，使同目录下带/不带黑窗的两个 exe 路径一致

  避免误替换路径中的目录名（如 C:\\my.win\\app\\xxx.exe）。
  """
  exe_dir, exe_filename = os.path.split(exe_path)
  exe_filename = exe_filename.replace('.win', '')
  return os.path.join(exe_dir, exe_filename)


@error_catch(error_msg='获取共享内存名异常', error_return='APP')
def get_memory_name() -> str:
  app_proc_pid = QApplication.applicationPid()
  app_proc = find_process(app_proc_pid)
  if not app_proc:
    return 'APP'

  # 统一去除 .win 后缀，使同目录下带/不带黑窗的两个 exe 共享同一个共享内存 key
  app_name = app_proc.name().replace('.win', '')
  # 使用可执行文件真实路径而非 CWD 拼路径，避免不同工作目录启动时 key 不同导致多开检测被绕过
  app_exe_path = app_proc.exe()
  if not app_exe_path:
    return create_md5(app_name)
  # 归一化 exe 路径（去除文件名中的 .win 后缀），保证两个 exe 生成相同 key
  memory_name = normalize_exe_path(app_exe_path)

  return create_md5(memory_name)


@error_catch(error_msg='查找正在运行的APP实例的进程pid异常', error_return=None)
def find_running_app_pid() -> Optional[int]:
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

  # 用于匹配的进程名去除 .win
  match_proc_name = app_proc_name.replace('.win', '')

  # 获取当前进程的归一化 exe 路径，用于校验是否为同目录下的同一应用
  app_exe_path = app_proc.exe()
  match_exe_path = normalize_exe_path(app_exe_path) if app_exe_path else ''

  # 收集所有匹配的候选进程，优先返回有窗口的进程
  candidates: List[int] = []
  for proc in psutil.process_iter(['pid', 'name']):
    try:
      name = proc.info['name'] or ''
      pid = proc.info['pid']
      # 确保不是当前进程，进程名相同
      if match_proc_name != name.replace('.win', '') or pid == app_proc_pid:
        continue

      # 校验 exe 路径是否一致（与 get_memory_name 逻辑保持同步），避免匹配到不同目录的同名应用
      if match_exe_path:
        proc_exe_path = proc.exe()
        if not proc_exe_path:
          continue
        if normalize_exe_path(proc_exe_path) != match_exe_path:
          continue

      APP_LOGGER.info(
        f'@@find_running_app_pid 找到的同名运行进程信息 pid: {proc.info["pid"]}  name: {proc.info["name"]}'
      )
      candidates.append(proc.info['pid'])
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
      APP_LOGGER.info(
        f'@@find_running_app_pid 遍历进程异常，跳过该进程 pid: {proc.info.get("pid")}  name: {proc.info.get("name")}  error: {e}'
      )

  if len(candidates) == 0:
    APP_LOGGER.info('@@find_running_app_pid 未找到的同名运行进程')
    return None

  # 优先返回有窗口的进程，避免匹配到 multiprocessing 子进程（子进程通常无窗口）
  for pid in candidates:
    if get_process_windows(pid):
      return pid

  # 所有候选都无窗口，返回第一个
  return candidates[0]


@error_catch(error_msg='将指定进程的窗口置顶异常', error_return=False)
def bring_to_front(pid: int) -> bool:
  """将指定进程的窗口置顶，返回是否成功找到并置顶了至少一个窗口"""
  hwnds = get_process_windows(pid)
  if len(hwnds) == 0:
    APP_LOGGER.info(f'@@bring_to_front 未找到进程 pid: {pid} 的可见窗口，可能仍在启动中或窗口被隐藏')
    return False
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
  return True


#  检查app运行文件路径是否合法（不包含中文字符）
def is_app_work_dir_valid() -> bool:
  app_work_dir = os.path.abspath(Path())
  if not os.path.exists(app_work_dir):
    return False

  # 检查路径中是否包含中文字符
  for char in app_work_dir:
    if '\u4e00' <= char <= '\u9fff':
      return False

  return True


def get_process_windows(pid: int) -> List[int]:
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
def get_mitmproxy_api_data_list(work_dir: str = '.', reverse: bool = False) -> List[ApiData]:
  mock_db: MockDB = MockDBCache.get(work_dir)
  return mock_db.get_api_list(query=ApiQuery(api_type='MITMPROXY'), reverse=reverse)


@error_catch(error_msg='读取 user api 数据失败', error_return=[])
def get_user_api_data_list(work_dir: str = '.', reverse: bool = False) -> List[ApiData]:
  mock_db: MockDB = MockDBCache.get(work_dir)
  return mock_db.get_api_list(query=ApiQuery(api_type='USER'), reverse=reverse)


@error_catch(error_msg='更新 user api 数据失败', error_return=False)
def update_user_api_data(work_dir: str = '.', update_data: Optional[ApiRecord] = None) -> bool:
  # 入参校验
  if not isinstance(update_data, dict):
    return False

  update_id = update_data.get('id', '')
  if not update_id:
    return False

  mock_db: MockDB = MockDBCache.get(work_dir)
  return mock_db.update_api(update_data)


@error_catch(error_msg='新增 user api 数据失败', error_return=False)
def add_user_api_data(work_dir: str = '.', add_data: Optional[Dict[str, Any]] = None) -> bool:
  if not isinstance(add_data, dict):
    return False

  record = {
    "type": add_data.get('type', 'USER'),
    "url": add_data.get('url', ''),
    "method": add_data.get('method', 'GET'),
    "params": add_data.get('params', JsonFormat.dumps({})),
    "response": add_data.get('response', JsonFormat.dumps({})),
  }
  mock_db: MockDB = MockDBCache.get(work_dir)
  mock_db.insert_api(record)
  return True


@error_catch(error_msg='删除 user api 数据失败', error_return=False)
def delete_user_api_data(work_dir: str = '.', delete_id: str = '') -> bool:
  if not isinstance(delete_id, str) or not delete_id:
    return False

  mock_db: MockDB = MockDBCache.get(work_dir)
  return mock_db.delete_api(delete_id)


@error_catch(error_msg='读取 api 数据文件失败', error_return=[])
def get_mock_api_data_list(work_dir: str = '.', enabled: Optional[bool] = None) -> List[ApiData]:
  mock_db: MockDB = MockDBCache.get(work_dir)
  api_list = mock_db.get_api_list(
    query=ApiQuery(api_type='MITMPROXY', enabled=enabled),
    reverse=False,
  )
  api_list.extend(mock_db.get_api_list(
    query=ApiQuery(api_type='USER', enabled=enabled),
    reverse=False),
  )

  return api_list


# 打开操作手册
@error_catch(error_msg='打开操作手册html失败', error_return=False)
def open_operation_manual_html(root_dir: str = '.') -> bool:
  base_path = f"{root_dir}/appServer/static/web"
  operation_manual_html = f"{base_path}/apps/document/index.html"
  if not os.path.exists(operation_manual_html):
    return False
  webbrowser.open(os.path.abspath(operation_manual_html))
  return True


@error_catch(error_msg='批量设置菜单元素配置失败')
def set_menu_config(menu: Optional[QMenu], config_list: List[Dict[str, Any]]) -> None:
  def menu_action_callback(action: QAction) -> None:
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
def set_menu_item_disabled(menu: Optional[QMenu], disable_list: List[Dict[str, Any]]) -> None:
  if not menu or not len(disable_list):
    return

  # 构造菜单元素禁用状态字典
  disable_dict: Dict[str, bool] = {}
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
def is_app_server_running(app_sever_running_data: Optional[AppServerRunningData]) -> bool:
  if not isinstance(app_sever_running_data, dict):
    return False

  success = app_sever_running_data.get('success', False)
  port = app_sever_running_data.get('port', 5050)
  if not success:
    return False

  if is_local_server_running(port=port, retry=0, retry_condition='NOT_RUNNING', caller='APP_SERVER_CHECK'):
    print(f"检测到 APP_SERVER 运行中！port={port}")
    return True
  else:
    APP_LOGGER.error(f"检测到 APP_SERVER 未运行！port={port}")
    return False
