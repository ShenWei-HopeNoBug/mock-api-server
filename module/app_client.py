# -*- coding: utf-8 -*-
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QMessageBox, QMainWindow, QFileDialog, QAction)

import os
import time
import requests
from config import globals
from qt_ui.mian_window import Ui_MainWindow
from module.mock_server import MockServer
from module.asyncio_mitmproxy_server import start_mitmproxy
from multiprocessing import Process
from lib.decorate import create_thread, error_catch
from lib.utils_lib import check_local_connection
from lib.work_file_lib import (check_work_files, create_work_files)
from lib.app_lib import open_mitmproxy_preview_html
from config.work_file import DEFAULT_WORK_DIR
from lib.system_lib import (GLOBALS_CONFIG_MANAGER, HISTORY_CONFIG_MANAGER)
import ENV


# mock 服务进程启动
def server_process_start(server_config: dict):
  print('server_config', server_config)
  read_cache = server_config.get('read_cache', False)
  port = server_config.get('port', 5000)
  work_dir = server_config.get('work_dir', '.')
  response_delay = server_config.get('response_delay', 0)
  static_load_speed = server_config.get('static_load_speed', 0)
  # 初始化 mock 服务实例
  server = MockServer(
    work_dir=work_dir,
    port=port,
    response_delay=response_delay,
    static_load_speed=static_load_speed,
  )
  # 启动本地 mock 服务
  server.start_server(read_cache=read_cache)


# app 主窗口
class MainWindow(QMainWindow, Ui_MainWindow):
  # 抓包服务运行信号
  catch_server_running_signal = pyqtSignal(bool)
  # 是否追加抓包信号
  use_history_signal = pyqtSignal(bool)
  # 下载静态资源信号
  downloading_signal = pyqtSignal(str)
  # mock 服务运行信号
  server_status_signal = pyqtSignal(str)

  def __init__(self):
    super().__init__()
    # 初始化全局变量文件
    GLOBALS_CONFIG_MANAGER.init(replace=True)
    # 初始化历史数据文件
    HISTORY_CONFIG_MANAGER.init(replace=False)
    # 获取历史工作目录
    work_dir = HISTORY_CONFIG_MANAGER.get(key='work_dir') or DEFAULT_WORK_DIR

    # 服务工作目录
    self.work_dir = work_dir
    # 抓包服务端口号
    self.catch_server_port = 8080
    # 抓包服务是否启动
    self.catch_server_running = False
    # 是否以追加模式抓包
    self.use_history = True
    # 下载静态资源是否压缩图片
    self.compress_image = True
    # -----------------
    # 静态资源下载状态
    # READY：待运行
    # DOWNLOAD：下载中
    # STOP_WAIT：待停止下载
    # -----------------
    self.download_status = 'READY'
    # -----------------
    # mock服务运行状态
    # READY：待运行
    # RUNNING：运行中
    # STOP_WAIT：待停止运行
    # -----------------
    self.server_status = 'READY'
    # 服务端口号
    self.server_port = 5000
    # 接口响应延时
    self.response_delay = 0
    # 静态资源请求加载速率
    self.static_load_speed = 0
    # 是否以缓存模式启动服务
    self.cache = False
    # 文件菜单对象
    self.file_menu = None

    self.init_ui()
    self.render_menu_bar()
    self.add_events()

  def init(self):
    # 用户拒绝在历史工作目录创建文件，切到默认工作目录
    if not self.check_and_create_work_files(self.work_dir):
      create_work_files(DEFAULT_WORK_DIR)
      # 更新工作目录历史记录
      HISTORY_CONFIG_MANAGER.set(key='work_dir', value=DEFAULT_WORK_DIR)
      self.work_dir = DEFAULT_WORK_DIR

  # 初始化窗口 UI
  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowTitle('mock server {}'.format(globals.version))

  # 渲染菜单栏
  def render_menu_bar(self):
    # 打开工作目录
    def open_work_dir():
      if not os.path.exists(self.work_dir):
        return

      os.startfile(os.path.abspath(self.work_dir))

    # 选择工作目录
    def select_work_dir():
      directory = QFileDialog.getExistingDirectory(self, '选择工作目录', r'./')
      if directory and self.check_and_create_work_files(directory):
        # 更换工作目录后，检查目录文件
        self.work_dir = directory
        self.serverWorkDirLineEdit.setText(self.work_dir)
        self.serverWorkDirLineEdit.setToolTip(self.work_dir)
        # 更新工作目录历史记录
        HISTORY_CONFIG_MANAGER.set(key='work_dir', value=self.work_dir)

    # 匹配菜单 action 类型
    def file_menu_action(action):
      action_name = action.text()
      if action_name == '更换工作目录':
        select_work_dir()
      elif action_name == '打开工作目录':
        open_work_dir()

    menu_bar = self.menuBar()
    file_menu = menu_bar.addMenu('文件')
    self.file_menu = file_menu
    file_menu.addAction('更换工作目录')
    file_menu.addAction('打开工作目录')
    file_menu.triggered[QAction].connect(file_menu_action)

  def add_events(self):
    # 监听信号变化
    self.server_status_signal.connect(self.server_status_change)
    self.downloading_signal.connect(self.downloading_change)
    self.catch_server_running_signal.connect(self.catch_server_running_change)
    '''
    按钮事件绑定
    '''

    def catch_server_port_change(value):
      self.catch_server_port = value

    def use_history_checkbox_click():
      self.use_history = not self.use_history

    def data_preview_button_click():
      result = open_mitmproxy_preview_html(root_dir='.', work_dir=self.work_dir)
      # 打开失败
      if not result:
        QMessageBox.critical(self, '异常', '打开抓包数据预览html失败！')

    def cache_checkbox_click():
      self.cache = not self.cache

    def compress_image_button_click():
      self.compress_image = not self.compress_image

    def static_download_button_click():
      self.download_static()

    def server_port_change(value):
      self.server_port = value

    def response_delay_change(value):
      self.response_delay = value

    def static_load_speed_change(value):
      self.static_load_speed = value

    # 端口号输入绑定
    self.catchServerPortSpinBox.setValue(self.catch_server_port)
    self.catchServerPortSpinBox.valueChanged.connect(catch_server_port_change)
    self.serverPortSpinBox.setValue(self.server_port)
    self.serverPortSpinBox.valueChanged.connect(server_port_change)
    self.responseDelaySpinBox.setValue(self.response_delay)
    self.responseDelaySpinBox.valueChanged.connect(response_delay_change)
    self.staticLoadSpeedSpinBox.setValue(self.static_load_speed)
    self.staticLoadSpeedSpinBox.valueChanged.connect(static_load_speed_change)
    # 抓包服务按钮
    self.catchServerButton.clicked.connect(self.catch_server_button_click)
    # 抓包是否采用追加模式
    self.useHistoryCheckBox.setChecked(self.use_history)
    self.useHistoryCheckBox.clicked.connect(use_history_checkbox_click)
    # 打开抓包数据预览html
    self.dataPreviewButton.clicked.connect(data_preview_button_click)
    # 压缩静态资源按钮
    self.compressCheckBox.setChecked(self.compress_image)
    self.compressCheckBox.clicked.connect(compress_image_button_click)
    self.staticDownloadButton.clicked.connect(static_download_button_click)
    # 缓存模式启动按钮
    self.cacheCheckBox.setChecked(self.cache)
    self.cacheCheckBox.clicked.connect(cache_checkbox_click)
    # mock 服务按钮
    self.serverButton.clicked.connect(self.server_button_click)

    # 选择服务的工作目录
    self.serverWorkDirLineEdit.setText(self.work_dir)
    self.serverWorkDirLineEdit.setToolTip(self.work_dir)

  @error_catch(error_msg='更新【文件】菜单子按钮禁用状态失败')
  def set_file_menu_disabled(self, action_name: str = '', disabled: bool = False):
    if not self.file_menu:
      return

    actions = self.file_menu.actions()
    target = None
    for action in actions:
      if action.text() == action_name:
        target = action
        break

    if target:
      target.setEnabled(not disabled)

  # mock 服务启动状态变化
  def server_status_change(self, text):
    self.server_status = text

    button_text: str = ''
    disabled: bool = False
    server_btn_disabled: bool = False

    if text == 'RUNNING':
      button_text = '停止服务'
      disabled = True
      server_btn_disabled = False
    elif text == 'STOP_WAIT':
      button_text = '正在停止...'
      disabled = True
      server_btn_disabled = True
    elif text == 'READY':
      button_text = '启动服务'
      disabled = False
      server_btn_disabled = False

    self.server_status = text

    self.serverButton.setText(button_text)
    self.serverButton.setDisabled(server_btn_disabled)

    self.cacheCheckBox.setDisabled(disabled)
    self.serverPortSpinBox.setDisabled(disabled)
    self.responseDelaySpinBox.setDisabled(disabled)
    self.staticLoadSpeedSpinBox.setDisabled(disabled)
    self.cacheCheckBox.setDisabled(disabled)
    self.set_file_menu_disabled(action_name='更换工作目录', disabled=disabled)
    # mock 服务启动时禁止启动抓包服务
    self.catchServerButton.setDisabled(disabled)

  # 下载状态变化
  def downloading_change(self, text):
    # 下载中
    if text == 'DOWNLOAD':
      download_btn_disabled = False
      disabled = True
      button_text = '停止资源下载'
    # 正在停止下载
    elif text == 'STOP_WAIT':
      download_btn_disabled = True
      disabled = False
      button_text = '正在停止...'
    # 初始化状态
    else:
      download_btn_disabled = False
      disabled = False
      button_text = '静态资源下载'

    self.download_status = text
    self.staticDownloadButton.setText(button_text)
    self.staticDownloadButton.setDisabled(download_btn_disabled)
    self.compressCheckBox.setDisabled(disabled)
    self.set_file_menu_disabled(action_name='更换工作目录', disabled=disabled)

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
    self.set_file_menu_disabled(action_name='更换工作目录', disabled=disabled)
    self.dataPreviewButton.setDisabled(disabled)
    # 抓包服务启动时禁止启动 mock 服务
    self.serverButton.setDisabled(disabled)

  def server_button_click(self):
    if self.server_status == 'READY':
      self.start_server()
    elif self.server_status == 'RUNNING':
      self.stop_server()
    time.sleep(0.5)

  def catch_server_button_click(self):
    self.stop_catch_server() if self.catch_server_running else self.start_catch_server()
    time.sleep(0.5)

  # 检查工作目录文件完整性
  def check_and_create_work_files(self, work_dir=DEFAULT_WORK_DIR):
    # 检查目录文件完整性
    if check_work_files(work_dir):
      return True

    reply = QMessageBox.question(
      self,
      '消息',
      '应用工作目录文件完整性检查未通过，是否创建工作目录文件？\n当前工作目录：{}'.format(
        os.path.abspath(work_dir),
      ),
      QMessageBox.Yes | QMessageBox.No,
      QMessageBox.No,
    )

    if reply == QMessageBox.Yes:
      # 创建工作文件
      create_work_files(work_dir)
      return True
    else:
      return False

  # 启动抓包服务
  def start_catch_server(self):
    mitmproxy_stop_signal = GLOBALS_CONFIG_MANAGER.get(key='mitmproxy_stop_signal')
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
      "work_dir": self.work_dir,
      "use_history": self.use_history,
      "mitmproxy_log": ENV.mitmproxy_log,
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
    mitmproxy_stop_signal = GLOBALS_CONFIG_MANAGER.get(key='mitmproxy_stop_signal')
    # 抓包服务还在停止中，跳过
    if mitmproxy_stop_signal:
      return

    if not self.catch_server_running:
      return
    # 设置全局 mitmproxy 服务停止信号
    GLOBALS_CONFIG_MANAGER.set(key='mitmproxy_stop_signal', value=True)
    # 向 mitmproxy 抓包服务发送一个本地请求，触发 addons 脚本内关闭服务事件
    requests.get('http://127.0.0.1:{}/index.html'.format(self.catch_server_port))
    self.catch_server_running_signal.emit(False)

  # 下载静态资源
  @create_thread
  def download_static(self):
    # 正在下载中
    if self.download_status == 'DOWNLOAD':
      self.downloading_signal.emit('STOP_WAIT')
      GLOBALS_CONFIG_MANAGER.set(key='download_exit', value=True)
      time.sleep(0.5)
      return

    server = MockServer(work_dir=self.work_dir, port=self.server_port)
    self.downloading_signal.emit('DOWNLOAD')
    GLOBALS_CONFIG_MANAGER.set(key='download_exit', value=False)
    server.download_static(compress=self.compress_image)
    # 下载任务结束后切换按钮显示
    GLOBALS_CONFIG_MANAGER.set(key='download_exit', value=False)
    time.sleep(0.5)
    self.downloading_signal.emit('READY')

  # 启动mock服务
  def start_server(self):
    # 服务不处于待启动状态，跳过
    if not self.server_status == 'READY':
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
      "work_dir": self.work_dir,
      "port": self.server_port,
      "read_cache": self.cache,
      "response_delay": self.response_delay,
      "static_load_speed": self.static_load_speed,
    }
    server_process = Process(
      target=server_process_start,
      args=(server_config,),
      name='mock_server',
    )
    server_process.start()
    self.server_status_signal.emit('RUNNING')

  # 停止mock服务
  @create_thread
  def stop_server(self):
    # 服务没在运行中，跳过
    if not self.server_status == 'RUNNING':
      return

    @error_catch(print_error_msg=False)
    def shutdown():
      """这个请求发送到 mock 服务后，会触发关闭服务进程，没有响应一定会报错，这里就不打印捕获错误信息了"""
      requests.get('http://127.0.0.1:{}/system/shutdown'.format(self.server_port))

    self.server_status_signal.emit('STOP_WAIT')
    shutdown()
    time.sleep(2)
    self.server_status_signal.emit('READY')

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
      GLOBALS_CONFIG_MANAGER.set(key='client_exit', value=True)
      time.sleep(0.2)
      event.accept()
    else:
      event.ignore()
