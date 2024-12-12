# -*- coding: utf-8 -*-
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QMainWindow

from qt_ui.mian_window import Ui_MainWindow
from mock_server import MockServer
from multiprocessing import Process
from decorate import create_thread
import time
import global_var
from request_catch import MitmdumpServer

# 抓包服务实例
mitmdump_server = MitmdumpServer()
# mock 服务实例
mock_server = MockServer()

def mitmdump_server_process_start(port=8080):
  if mitmdump_server:
    # 启动本地抓包服务
    mitmdump_server.start_server(port)

def server_process_start(cache=False):
  if mock_server:
    # 启动本地 mock 服务
    mock_server.start_server(cache)

# app 主窗口
class MainWindow(QMainWindow, Ui_MainWindow):
  # 抓包服务运行信号
  catch_server_running_signal = pyqtSignal(bool)
  # 下载静态资源信号
  downloading_signal = pyqtSignal(bool)
  # mock 服务运行信号
  server_running_signal = pyqtSignal(bool)

  def __init__(self):
    super().__init__()
    # 抓包服务端口号
    self.catch_server_port = 8080
    # 抓包服务是否启动
    self.catch_server_running = False
    # 下载静态资源是否压缩图片
    self.compress_image = True
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
    self.setWindowTitle('mock server v0.0.2')

  def add_events(self):
    # 监听信号变化
    self.server_running_signal.connect(self.server_running_change)
    self.downloading_signal.connect(self.downloading_change)
    self.catch_server_running_signal.connect(self.catch_server_running_change)
    '''
    按钮事件绑定
    '''
    def catch_server_port_change(value):
      self.catch_server_port = value

    self.catchServerPortSpinBox.valueChanged.connect(catch_server_port_change)
    # 抓包服务按钮
    self.catchServerButton.clicked.connect(self.catch_server_button_click)
    # 压缩静态资源按钮
    self.compressCheckBox.setChecked(self.compress_image)
    self.compressCheckBox.clicked.connect(self.compress_image_button_click)
    self.staticDownloadButton.clicked.connect(self.static_download_button_click)
    # 缓存模式启动按钮
    self.cacheCheckBox.setChecked(self.cache)
    self.cacheCheckBox.clicked.connect(self.cache_checkbox_click)
    # mock 服务按钮
    self.serverButton.clicked.connect(self.server_button_click)

  def server_running_change(self, value):
    if self.server_running == value:
      return

    self.server_running = value
    if value:
      button_text = '停止服务'
      disabled = True
    else:
      button_text = '启动服务'
      disabled = False
    self.serverButton.setText(button_text)
    self.cacheCheckBox.setDisabled(disabled)

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
    self.compressCheckBox.setDisabled(disabled)
    self.staticDownloadButton.setDisabled(disabled)

  def catch_server_running_change(self, value):
    if self.catch_server_running == value:
      return
    self.catch_server_running = value
    if value:
      button_text = '停止抓包服务'
      disabled = True
    else:
      button_text = '启动抓包服务'
      disabled = False
    self.catchServerButton.setText(button_text)
    self.catchServerPortSpinBox.setDisabled(disabled)

  def compress_image_button_click(self):
    self.compress_image = not self.compress_image

  def static_download_button_click(self):
    self.static_download()

  def cache_checkbox_click(self):
    self.cache = not self.cache

  def server_button_click(self):
    self.stop_server() if self.server_running else self.start_server()
    time.sleep(0.5)

  def catch_server_button_click(self):
    self.stop_catch_server() if self.catch_server_running else self.start_catch_server()
    time.sleep(0.5)

  # 启动抓包服务
  def start_catch_server(self):
    if self.catch_server_running:
      return

    print('start_catch_server', mitmdump_server)
    server_process = Process(
      target=mitmdump_server_process_start,
      args=(self.catch_server_port,),
      name='mitmdump_server',
    )
    server_process.start()
    self.catch_server_running_signal.emit(True)

  # 停止抓包服务
  def stop_catch_server(self):
    if not self.catch_server_running:
      return
    print('stop_catch_server', mitmdump_server)
    mitmdump_server.stop_server()
    self.catch_server_running_signal.emit(False)

  # 下载静态资源
  @create_thread
  def static_download(self):
    # 服务没初始化或正在下载中，跳过
    if not mock_server or self.downloading:
      return

    self.downloading_signal.emit(True)
    mock_server.check_static(compress=self.compress_image)
    self.downloading_signal.emit(False)
    time.sleep(0.5)

  # 启动mock服务
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

  # 停止mock服务
  def stop_server(self):
    if not self.server_running:
      return

    if mock_server:
      mock_server.stop_server()
    self.server_running_signal.emit(False)

  # 重写弹窗关闭事件
  def closeEvent(self, event: QCloseEvent):
    reply = QMessageBox.question(
      self,
      '消息',
      '确定要退出吗？',
      QMessageBox.Yes | QMessageBox.No,
      QMessageBox.No,
    )

    if reply == QMessageBox.Yes:
      # 尝试杀掉运行的服务进程
      self.stop_catch_server()
      self.stop_server()
      # 设置退出程序的全局变量
      global_var.global_exit = True
      event.accept()
    else:
      event.ignore()
