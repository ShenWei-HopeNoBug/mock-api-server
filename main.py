# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtCore import Qt

import sys
import time
import threading
import multiprocessing
import traceback as tb_module
from types import TracebackType
from typing import Any, Callable, Optional, Type

from module.app_server import start_app_server
from lib.splash import StartSplash
from qt_win.app import MainWindow
from lib.logger_lib import APP_LOGGER
from lib.app_lib import (
  get_memory_name,
  is_app_running,
  find_running_app_pid,
  bring_to_front,
  is_app_work_dir_valid,
)
from app_types.app_gui_types import AppServerRunningData


def exception_handler(
    exception_type: Type[BaseException],
    value: BaseException,
    traceback: Optional[TracebackType],
) -> None:
  """全局异常处理器"""
  tb_str = ''.join(tb_module.format_exception(exception_type, value, traceback))
  APP_LOGGER.error(f'APP全局程序异常捕获：{value}\n{tb_str}')
  # 显示异常信息的对话框
  QMessageBox.critical(None, "程序异常", f"发生异常：{value}")
  sys.exit(1)


def run_blocking_with_events(app: QApplication, func: Callable, *args: Any, **kwargs: Any) -> Any:
  """在子线程中执行阻塞函数，主线程持续处理事件以保持 UI 响应"""
  result: list = [None]
  done = threading.Event()

  def wrapper() -> None:
    result[0] = func(*args, **kwargs)
    done.set()

  t = threading.Thread(target=wrapper, daemon=True)
  t.start()

  while not done.is_set():
    app.processEvents()
    time.sleep(0.02)

  return result[0]


if __name__ == '__main__':
  # 防止窗口开进程新打开个 GUI 窗口
  multiprocessing.freeze_support()
  # 禁止屏幕设置了缩放导致显示不一致
  QGuiApplication.setAttribute(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
  app: QApplication = QApplication(sys.argv)
  # 全局异常捕获
  sys.excepthook = exception_handler

  # 检查 APP 是否已经在运行
  if is_app_running(app_name=get_memory_name()):
    # 查找已运行的实例
    pid: Optional[int] = find_running_app_pid()
    if pid:
      # 将已运行的实例窗口置顶
      bring_to_front(pid)
    QMessageBox.information(None, '提示', '程序已经在运行中！')
    sys.exit(1)

  # 检查 APP 运行路径是否合法
  if not is_app_work_dir_valid():
    QMessageBox.critical(None, '程序异常', '程序运行路径异常（路径包含中文或路径不存在）！')
    sys.exit(1)

  start_splash: StartSplash = StartSplash()
  # 启动动画对象
  start_splash.show()
  # 确保启动动画立即渲染
  app.processEvents()

  # 启动 APP_SERVER 服务（子线程执行，主线程保持事件循环以更新启动动画）
  app_sever_running_data: AppServerRunningData = run_blocking_with_events(app, start_app_server)

  # app 主窗口
  main_window: MainWindow = MainWindow(app_sever_running_data=app_sever_running_data)
  app.processEvents()

  # 展示窗口
  main_window.show()
  app.processEvents()

  # 结束启动动画，动画结束后执行 init
  start_splash.finish(main_window, callback=main_window.init)

  sys.exit(app.exec_())
