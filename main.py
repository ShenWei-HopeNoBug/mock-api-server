# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QApplication, QMessageBox

import sys
import multiprocessing
from lib.splash import StartSplash
from qt_win.app import MainWindow


def exception_handler(exception_type, value):
  """全局异常处理器"""
  # 显示异常信息的对话框
  QMessageBox.critical(None, "程序异常", f"发生异常：{value}")
  sys.exit(1)


if __name__ == '__main__':
  # 防止窗口开进程新打开个 GUI 窗口
  multiprocessing.freeze_support()
  app = QApplication(sys.argv)
  # 全局异常捕获
  sys.excepthook = exception_handler

  start_splash = StartSplash()
  # 启动动画对象
  start_splash.show()
  # 防止启动动画卡住主进程
  app.processEvents()

  # app 主窗口
  main_window = MainWindow()
  # 展示窗口
  main_window.show()
  # 结束启动动画
  start_splash.finish(main_window)
  start_splash = None
  # 初始化
  main_window.init()

  sys.exit(app.exec_())
