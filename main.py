# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtCore import Qt

import sys
import requests
import multiprocessing
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
from module.app_server import AppServer
from lib.decorate import create_thread
from multiprocessing import Process


def exception_handler(exception_type, value):
  """全局异常处理器"""
  APP_LOGGER.error(f'APP全局程序异常捕获：{value}')
  # 显示异常信息的对话框
  QMessageBox.critical(None, "程序异常", f"发生异常：{value}")
  sys.exit(1)


# app 服务进程启动
def app_server_process_start(server_config: dict):
  port = server_config.get('port', 5007)
  app_server = AppServer(port=port)
  app_server.start()


@create_thread
def start_app_server():
  server_config = {
    "port": 5007,
  }

  app_server_process = Process(
    target=app_server_process_start,
    args=(server_config,),
    name='app_server_process',
  )

  # 启动进程 APP 服务进程
  app_server_process.start()


if __name__ == '__main__':
  # 防止窗口开进程新打开个 GUI 窗口
  multiprocessing.freeze_support()
  # 禁止屏幕设置了缩放导致显示不一致
  QGuiApplication.setAttribute(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
  app = QApplication(sys.argv)
  # 全局异常捕获
  sys.excepthook = exception_handler

  # 检查 APP 是否已经在运行
  if is_app_running(app_name=get_memory_name()):
    # 查找已运行的实例
    pid = find_running_app_pid()
    if pid:
      # 将已运行的实例窗口置顶
      bring_to_front(pid)
    QMessageBox.information(None, '提示', '程序已经在运行中！')
    sys.exit(1)

  # 检查 APP 运行路径是否合法
  if not is_app_work_dir_valid():
    QMessageBox.critical(None, '程序异常', '程序运行路径异常（路径包含中文或路径不存在）！')
    sys.exit(1)

  start_splash = StartSplash()
  # 启动动画对象
  start_splash.show()
  # 防止启动动画卡住主进程
  app.processEvents()

  # app 主窗口
  main_window = MainWindow()

  # app_server_port = 5007
  # start_app_server()
  # app_server_running = False
  # check_count = 0
  # while not app_server_running and check_count < 10:
  #   try:
  #     response = requests.get('http://127.0.0.1:{}/ping'.format(app_server_port))
  #     if response.status_code == 200:
  #       app_server_running = True
  #     else:
  #       check_count += 1
  #   except Exception as e:
  #     print('APP_SERVER 未启动！', e)
  #     check_count += 1

  # 展示窗口
  main_window.show()
  # 结束启动动画
  start_splash.finish(main_window)
  start_splash = None
  # 初始化
  main_window.init()

  sys.exit(app.exec_())
