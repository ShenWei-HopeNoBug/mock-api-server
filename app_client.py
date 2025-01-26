# -*- coding: utf-8 -*-
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QMainWindow, QFileDialog

import time
import requests
import global_var
from qt_ui.mian_window import Ui_MainWindow
from mock_server import MockServer
from multiprocessing import Process
from decorate import create_thread, error_catch
from utils import check_local_connection
from asyncio_mitmproxy_server import start_mitmproxy


# mock 服务进程启动
def server_process_start(server_config: dict):
  print('server_config', server_config)
  read_cache = server_config.get('read_cache', False)
  port = server_config.get('port', 5000)
  work_dir = server_config.get('work_dir', '.')
  server = MockServer(work_dir=work_dir, port=port)
  # 启动本地 mock 服务
  server.start_server(read_cache=read_cache)


# app 主窗口
class MainWindow(QMainWindow, Ui_MainWindow):
  # 抓包服务运行信号
  catch_server_running_signal = pyqtSignal(bool)
  # 是否追加抓包信号
  use_history_signal = pyqtSignal(bool)
  # 下载静态资源信号
  downloading_signal = pyqtSignal(bool)
  # mock 服务运行信号
  server_running_signal = pyqtSignal(bool)

  def __init__(self):
    super().__init__()
    # 初始化全局变量文件
    global_var.init()

    # 抓包服务端口号
    self.catch_server_port = 8080
    # 抓包服务是否启动
    self.catch_server_running = False
    # 是否以追加模式抓包
    self.use_history = True
    # 下载静态资源是否压缩图片
    self.compress_image = True
    # 是否正在下载静态资源
    self.downloading = False
    # 服务工作目录
    self.server_work_dir = './server'
    # 服务是否正在运行
    self.server_running = False
    # 服务端口号
    self.server_port = 5000
    # 是否以缓存模式启动服务
    self.cache = False

    self.init_ui()
    self.add_events()

  # 初始化窗口 UI
  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowTitle('mock server {}'.format(global_var.version))

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

    def use_history_checkbox_click():
      self.use_history = not self.use_history

    def cache_checkbox_click():
      self.cache = not self.cache

    def compress_image_button_click():
      self.compress_image = not self.compress_image

    def static_download_button_click():
      self.static_download()

    def server_port_change(value):
      self.server_port = value

    # 端口号输入绑定
    self.catchServerPortSpinBox.setValue(self.catch_server_port)
    self.catchServerPortSpinBox.valueChanged.connect(catch_server_port_change)
    self.serverPortSpinBox.setValue(self.server_port)
    self.serverPortSpinBox.valueChanged.connect(server_port_change)
    # 抓包服务按钮
    self.catchServerButton.clicked.connect(self.catch_server_button_click)
    # 抓包是否采用追加模式
    self.useHistoryCheckBox.setChecked(self.use_history)
    self.useHistoryCheckBox.clicked.connect(use_history_checkbox_click)
    # 压缩静态资源按钮
    self.compressCheckBox.setChecked(self.compress_image)
    self.compressCheckBox.clicked.connect(compress_image_button_click)
    self.staticDownloadButton.clicked.connect(static_download_button_click)
    # 缓存模式启动按钮
    self.cacheCheckBox.setChecked(self.cache)
    self.cacheCheckBox.clicked.connect(cache_checkbox_click)
    # mock 服务按钮
    self.serverButton.clicked.connect(self.server_button_click)

    # 选择文件夹
    def select_directory():
      directory = QFileDialog.getExistingDirectory(self, '选择工作目录', r'./')
      if directory:
        self.server_work_dir = directory
        self.serverWorkDirLineEdit.setText(self.server_work_dir)

    # 选择服务的工作目录
    self.serverWorkDirLineEdit.setText(self.server_work_dir)
    self.severWorkDirBrowsePushButton.clicked.connect(select_directory)

  # mock 服务启动状态变化
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
    self.serverPortSpinBox.setDisabled(disabled)
    self.cacheCheckBox.setDisabled(disabled)
    self.severWorkDirBrowsePushButton.setDisabled(disabled)
    # mock 服务启动时禁止启动抓包服务
    self.catchServerButton.setDisabled(disabled)

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
    self.severWorkDirBrowsePushButton.setDisabled(disabled)

  # 抓包服务启动状态变化
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
    self.useHistoryCheckBox.setDisabled(disabled)
    self.severWorkDirBrowsePushButton.setDisabled(disabled)
    # 抓包服务启动时禁止启动 mock 服务
    self.serverButton.setDisabled(disabled)

  def server_button_click(self):
    self.stop_server() if self.server_running else self.start_server()
    time.sleep(0.5)

  def catch_server_button_click(self):
    self.stop_catch_server() if self.catch_server_running else self.start_catch_server()
    time.sleep(0.5)

  # 启动抓包服务
  def start_catch_server(self):
    mitmproxy_stop_signal = global_var.get_global_var(key='mitmproxy_stop_signal')
    # 抓包服务还在停止中，跳过
    if mitmproxy_stop_signal:
      return

    if self.catch_server_running:
      return

    # 网络监听端口检查
    if check_local_connection('0.0.0.0', self.catch_server_port):
      QMessageBox.critical(
        self,
        '端口检查',
        '{} 端口已被占用，启动抓包服务失败！'.format(self.catch_server_port),
      )
      return

    # 抓包服务启动配置
    mitmproxy_config = {
      "host": "0.0.0.0",
      "port": self.catch_server_port,
      "work_dir": self.server_work_dir,
      "use_history": self.use_history,
    }

    server_process = Process(
      target=start_mitmproxy,
      args=(mitmproxy_config,),
      name='mitmdump_server',
    )
    server_process.start()
    self.catch_server_running_signal.emit(True)

  # 停止抓包服务
  def stop_catch_server(self):
    mitmproxy_stop_signal = global_var.get_global_var(key='mitmproxy_stop_signal')
    # 抓包服务还在停止中，跳过
    if mitmproxy_stop_signal:
      return

    if not self.catch_server_running:
      return
    # 设置全局 mitmproxy 服务停止信号
    global_var.update_global_var(key='mitmproxy_stop_signal', value=True)
    # 向 mitmproxy 抓包服务发送一个本地请求，触发 addons 脚本内关闭服务事件
    requests.get('http://127.0.0.1:{}/index.html'.format(self.catch_server_port))
    self.catch_server_running_signal.emit(False)

  # 下载静态资源
  @create_thread
  def static_download(self):
    # 正在下载中，跳过
    if self.downloading:
      return

    server = MockServer(work_dir=self.server_work_dir, port=self.server_port)
    self.downloading_signal.emit(True)
    server.check_static(compress=self.compress_image)
    self.downloading_signal.emit(False)
    time.sleep(0.5)

  # 启动mock服务
  def start_server(self):
    if self.server_running:
      return

    # 网络监听端口检查
    if check_local_connection('0.0.0.0', self.server_port):
      QMessageBox.critical(
        self,
        '端口检查',
        '{} 端口已被占用，启动 mock 服务失败！'.format(self.server_port),
      )
      return

    server_config = {
      "work_dir": self.server_work_dir,
      "port": self.server_port,
      "read_cache": self.cache,
    }
    server_process = Process(
      target=server_process_start,
      args=(server_config,),
      name='mock_server',
    )
    server_process.start()
    self.server_running_signal.emit(True)

  # 停止mock服务
  def stop_server(self):
    if not self.server_running:
      return

    @error_catch(print_error_msg=False)
    def shutdown():
      '''这个请求发送到 mock 服务后，会触发关闭服务进程，没有响应一定会报错，这里就不打印捕获错误信息了'''
      requests.get('http://127.0.0.1:{}/system/shutdown'.format(self.server_port))

    shutdown()
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
      global_var.update_global_var(key='client_exit', value=True)
      time.sleep(0.2)
      event.accept()
    else:
      event.ignore()
