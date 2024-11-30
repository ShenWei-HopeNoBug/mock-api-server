# -*- coding: utf-8 -*-
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QMainWindow

from qt_ui.mian_window import Ui_MainWindow
from mock_server import MockServer
from multiprocessing import Process
from utils import create_thread
import time

mock_server = MockServer()


def server_process_start(cache=False):
  if mock_server:
    # 启本地 mock 服务
    mock_server.start_server(cache)


# app 主窗口
class MainWindow(QMainWindow, Ui_MainWindow):
  server_running_signal = pyqtSignal(bool)
  downloading_signal = pyqtSignal(bool)

  def __init__(self):
    super().__init__()
    # 是否正在下载静态资源
    self.downloading = False
    # 服务是否正在运行
    self.server_running = False
    # 是否以缓存模式启动服务
    self.cache = False

    self.init_ui()
    self.add_events()

  # 初始化窗口 UI
  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowTitle('mock server v0.0.1-bata')

  def add_events(self):
    # 监听信号变化
    self.server_running_signal.connect(self.server_running_change)
    self.downloading_signal.connect(self.downloading_change)
    # 按钮事件绑定
    self.staticDownloadButton.clicked.connect(self.static_download_button_click)
    self.cacheCheckBox.clicked.connect(self.cache_checkbox_clicked)
    self.serverButton.clicked.connect(self.server_button_click)

  def server_running_change(self, value):
    if self.server_running == value:
      return

    self.server_running = value
    if value:
      button_text = '停止服务'
    else:
      button_text = '启动服务'
    self.serverButton.setText(button_text)

  def downloading_change(self, value):
    if self.downloading == value:
      return

    self.downloading = value
    if value:
      disabled = True
      button_text = '静态资源下载中...'
    else:
      disabled = False
      button_text = '静态资源下载'
    self.staticDownloadButton.setText(button_text)
    self.staticDownloadButton.setDisabled(disabled)

  def static_download_button_click(self):
    self.static_download()

  def cache_checkbox_clicked(self):
    self.cache = not self.cache

  def server_button_click(self):
    self.stop_server() if self.server_running else self.start_server()
    time.sleep(0.5)

  # 下载静态资源
  @create_thread
  def static_download(self):
    print(self.downloading)
    # 服务没初始化或正在下载中，跳过
    if not mock_server or self.downloading:
      return

    self.downloading_signal.emit(True)
    mock_server.check_static()
    self.downloading_signal.emit(False)
    time.sleep(0.5)

  def start_server(self):
    if self.server_running:
      return

    server_process = Process(
      target=server_process_start,
      args=(self.cache,),
      name='mock_server',
    )
    server_process.start()
    self.server_running_signal.emit(True)

  def stop_server(self):
    if not self.server_running:
      return

    if mock_server:
      mock_server.stop_server()
    self.server_running_signal.emit(False)

  def closeEvent(self, event: QCloseEvent):
    reply = QMessageBox.question(
      self,
      '消息',
      '确定要退出吗？',
      QMessageBox.Yes | QMessageBox.No,
      QMessageBox.No,
    )

    if reply == QMessageBox.Yes:
      self.stop_server()
      event.accept()
    else:
      event.ignore()
