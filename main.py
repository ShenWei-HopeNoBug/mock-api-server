# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtCore import Qt

import sys
import multiprocessing
import traceback as tb_module
from types import TracebackType
from typing import Optional, Type

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
  # 防止启动动画卡住主进程
  app.processEvents()

  # 启动 APP_SERVER 服务
  app_sever_running_data: AppServerRunningData = start_app_server()

  # app 主窗口
  main_window: MainWindow = MainWindow(app_sever_running_data=app_sever_running_data)
  # 展示窗口
  main_window.show()
  # 结束启动动画
  start_splash.finish(main_window)
  # 初始化
  main_window.init()

  sys.exit(app.exec_())
