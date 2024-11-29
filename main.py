# -*- coding: utf-8 -*-
from app_client import MainWindow
from PyQt5.QtWidgets import QApplication, QMessageBox
import sys




def exception_handler(exception_type, value, traceback):
  """全局异常处理器"""
  # 显示异常信息的对话框
  QMessageBox.critical(None, "程序异常", f"发生异常：{value}")
  sys.exit(1)

if __name__ == '__main__':
  app = QApplication(sys.argv)
  sys.excepthook = exception_handler
  main_window = MainWindow()
  main_window.show()
  sys.exit(app.exec_())
