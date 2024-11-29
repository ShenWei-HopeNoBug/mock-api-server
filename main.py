# -*- coding: utf-8 -*-
from mock_server import MockServer
from app_client import MainWindow
from PyQt5.QtWidgets import QApplication
import sys

if __name__ == '__main__':
  # mock_server = MockServer()

  # 检查和下载静态资源
  # mock_server.check_static()

  # 启本地 mock 服务
  # mock_server.start_server()

  app = QApplication(sys.argv)
  main_window = MainWindow()
  main_window.show()
  sys.exit(app.exec_())
