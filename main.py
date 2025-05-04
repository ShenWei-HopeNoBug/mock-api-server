# -*- coding: utf-8 -*-
from module.app_client import MainWindow
from PyQt5.QtWidgets import QApplication, QMessageBox
import sys
import multiprocessing


def exception_handler(exception_type, value, traceback):
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
  # app 主窗口
  main_window = MainWindow()

  # 引入QSS样式文件
  # with open('./qt_style/index.qss', 'r', encoding='utf-8') as fl:
  #   styleSheet = fl.read()
  #   main_window.setStyleSheet(styleSheet)

  main_window.show()
  main_window.init()
  sys.exit(app.exec_())
