# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from PyQt5.QtGui import QCloseEvent, QResizeEvent
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (QMessageBox, QMainWindow, QFileDialog, QMenu, QApplication, QFrame, QLabel, QVBoxLayout,
                             QProgressBar)
import threading

from qt_win.output_static_dialog import OutputStaticDialog
from qt_win.about_dialog import AboutDialog
from qt_win.mitmproxy_config_dialog import MitmproxyConfigDialog
from qt_win.server_config_dialog import ServerConfigDialog
from qt_win.download_config_dialog import DownloadConfigDialog
from qt_win.mitmproxy_data_edit_dialog import MitmproxyDataEditDialog
from qt_win.download_proxy_config_dialog import DownloadProxyConfigDialog

import os
import time
import requests
from config import globals
from qt_ui.main_win.win_ui import Ui_MainWindow
from module.asyncio_mitmproxy_server import start_mitmproxy
from module.mcp_server import start_mcp_server
from multiprocessing import Process, Event
from multiprocessing.synchronize import Event as EventType
from lib.decorate import create_thread, error_catch
from lib.logger_lib import APP_LOGGER
from lib.utils_lib import check_local_connection, is_local_server_running
from lib.server_lib import server_process_start
from lib.work_file_lib import (check_work_files, create_work_files)
from lib.app_lib import (
  open_operation_manual_html,
  set_menu_config,
  set_menu_item_disabled,
  is_app_server_running,
)
from app_types.app_gui_types import AppServerRunningData
from app_types.mitmproxy_types import MitmproxyRunConfig
from app_types.mcp_server_types import McpServerRunConfig
from lib.db import MockDBCache
from lib.download_lib import download_server_static
from config.work_file import (DEFAULT_WORK_DIR, STATIC_DIR)
from config.menu import (FILE, EDIT, HELP)
from lib.system_lib import HISTORY_CONFIG_MANAGER
import app_env

from qt_ui.main_win import main_win_style


# app 主窗口
class MainWindow(QMainWindow, Ui_MainWindow):
  # 抓包服务运行信号
  mitmproxy_server_status_signal: pyqtSignal = pyqtSignal(str)
  # 下载静态资源信号
  downloading_signal: pyqtSignal = pyqtSignal(str)
  # mock 服务运行信号
  server_status_signal: pyqtSignal = pyqtSignal(str)
  # MCP 服务运行信号
  mcp_server_status_signal: pyqtSignal = pyqtSignal(str)
  # 提示弹窗信号
  message_dialog_signal: pyqtSignal = pyqtSignal(str, str, str)
  # 退出清理完成信号
  cleanup_done_signal: pyqtSignal = pyqtSignal()
  # 退出清理进度信号
  cleanup_progress_signal: pyqtSignal = pyqtSignal(str)

  def __init__(self, app_sever_running_data: Optional[AppServerRunningData] = None) -> None:
    super().__init__()
    # 初始化历史数据文件
    HISTORY_CONFIG_MANAGER.init(replace=False)
    # 获取历史工作目录
    work_dir = HISTORY_CONFIG_MANAGER.get(key='work_dir') or DEFAULT_WORK_DIR

    # 服务工作目录
    self.work_dir: str = os.path.abspath(work_dir)
    # 抓包服务端口号
    self.catch_server_port: int = 8080
    # -----------------
    # 抓包服务运行状态
    # READY：待运行
    # START_WAIT：正在开始
    # RUNNING：运行中
    # STOP_WAIT：正在停止
    # -----------------
    self.mitmproxy_server_status: str = 'READY'
    # 下载静态资源是否压缩图片
    self.compress_image: bool = True
    # -----------------
    # 静态资源下载状态
    # READY：待运行
    # DOWNLOAD：下载中
    # STOP_WAIT：正在停止
    # -----------------
    self.download_status: str = 'READY'
    # 下载停止事件（线程间通信，替代文件标志）
    self._download_stop_event: threading.Event = threading.Event()
    # -----------------
    # mock服务运行状态
    # READY：待运行
    # START_WAIT：正在开始
    # RUNNING：运行中
    # STOP_WAIT：正在停止
    # -----------------
    self.server_status: str = 'READY'
    # 下载详情
    self.download_detail: Dict[str, Any] = {}
    # 服务端口号
    self.server_port: int = 5000
    # 接口响应延时
    self.response_delay: int = 0
    # 静态资源请求加载速率
    self.static_load_speed: int = 0
    # 文件菜单对象
    self.file_menu: Optional[QMenu] = None
    # 编辑菜单对象
    self.edit_menu: Optional[QMenu] = None
    # APP 服务启动端口号
    self.app_sever_running_data: Optional[AppServerRunningData] = app_sever_running_data

    # mock 服务子进程引用
    self._mock_server_process: Optional[Process] = None
    # -----------------
    # MCP 服务运行状态
    # READY：待运行
    # START_WAIT：正在开始
    # RUNNING：运行中
    # STOP_WAIT：正在停止
    # -----------------
    self.mcp_server_status: str = 'READY'
    # MCP 服务端口号
    self.mcp_server_port: int = 8765
    # MCP 服务子进程引用
    self._mcp_server_process: Optional[Process] = None
    # MCP 停止信号 Event（跨进程）
    self._mcp_stop_event: Optional[EventType] = None
    # mitmproxy 子进程引用
    self.mitmproxy_process: Optional[Process] = None
    # mitmproxy 停止信号 Event（跨进程）
    self.mitmproxy_stop_event: Optional[EventType] = None
    # mitmproxy 就绪信号 Event（跨进程，子进程 running 钩子触发）
    self.mitmproxy_ready_event: Optional[EventType] = None
    # 退出蒙层
    self._exit_overlay: Optional[QFrame] = None
    self._exit_tip_label: Optional[QLabel] = None

    self.init_ui()
    self.render_menu_bar()
    self.add_events()

  # -----------------------------------
  # 初始化（窗口实例化后必须手动调用一次）
  # -----------------------------------
  def init(self) -> None:
    # 用户拒绝在历史工作目录创建文件，切到默认工作目录
    if not self.check_and_create_work_files(self.work_dir):
      work_dir = os.path.abspath(DEFAULT_WORK_DIR)
      create_work_files(work_dir)
      # 更新工作目录历史记录
      HISTORY_CONFIG_MANAGER.set(key='work_dir', value=work_dir)
      self.work_dir = work_dir

  # 初始化窗口 UI
  def init_ui(self) -> None:
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowTitle(f'Mock Server {globals.version}')
    self.setWindowOpacity(0.95)
    self.setStyleSheet(main_win_style.window)

  # 渲染菜单栏
  def render_menu_bar(self) -> None:
    menu_bar = self.menuBar()

    # ---------------------
    # 文件菜单相关初始化
    # ---------------------
    # 打开工作目录
    def open_work_dir():
      if not os.path.exists(self.work_dir):
        return

      os.startfile(os.path.abspath(self.work_dir))

    file_menu = menu_bar.addMenu(FILE.MENU_NAME)
    self.file_menu = file_menu
    set_menu_config(file_menu, [
      {"name": FILE.CHANGE_WORK_DIR, "callback": self.select_work_dir},
      {"name": FILE.OPEN_WORK_DIR, "callback": open_work_dir},
      {"name": FILE.OUTPUT_STATIC_FILE, "callback": self.output_static},
    ])

    # ---------------------
    # 编辑菜单相关初始化
    # ---------------------
    def open_mitmproxy_config_dialog():
      mitmproxy_config_dialog = MitmproxyConfigDialog(work_dir=self.work_dir)
      mitmproxy_config_dialog.exec_()

    def open_download_dialog():
      download_dialog = DownloadConfigDialog(work_dir=self.work_dir)
      download_dialog.exec_()

    def open_server_config_dialog():
      server_config_dialog = ServerConfigDialog(work_dir=self.work_dir)
      server_config_dialog.exec_()

    def open_mitmproxy_data_edit_dialog():
      mitmproxy_data_dialog = MitmproxyDataEditDialog(
        parent=self,
        work_dir=self.work_dir,
        app_sever_running_data=self.app_sever_running_data,
      )
      mitmproxy_data_dialog.setWindowModality(Qt.WindowModal)
      mitmproxy_data_dialog.show()

    def open_download_proxy_config_dialog():
      mitmproxy_data_dialog = DownloadProxyConfigDialog(
        parent=self,
        work_dir=self.work_dir,
        app_sever_running_data=self.app_sever_running_data,
      )
      mitmproxy_data_dialog.setWindowModality(Qt.WindowModal)
      mitmproxy_data_dialog.show()

    edit_menu = menu_bar.addMenu(EDIT.MENU_NAME)
    self.edit_menu = edit_menu
    set_menu_config(edit_menu, [
      {"name": EDIT.MITMPROXY_EDIT, "callback": open_mitmproxy_config_dialog},
      {"name": EDIT.DOWNLOAD_EDIT, "callback": open_download_dialog},
      {"name": EDIT.SERVER_EDIT, "callback": open_server_config_dialog},
      {"name": EDIT.MITMPROXY_DATA_EDIT, "callback": open_mitmproxy_data_edit_dialog},
      {"name": EDIT.DOWNLOAD_PROXY_EDIT, "callback": open_download_proxy_config_dialog},
    ])

    # ---------------------
    # 帮助菜单相关初始化
    # ---------------------
    def open_about_dialog():
      about_dialog = AboutDialog()
      about_dialog.exec_()

    def open_operation_manual():
      result = open_operation_manual_html()
      # 打开失败
      if not result:
        QMessageBox.critical(self, '异常', '打开操作手册html失败！')

    help_menu = menu_bar.addMenu(HELP.MENU_NAME)
    set_menu_config(help_menu, [
      {"name": HELP.OPERATION_MANUAL, "callback": open_operation_manual},
      {"name": HELP.ABOUT, "callback": open_about_dialog},
    ])

  # 绑定窗口事件
  def add_events(self) -> None:
    # 监听信号变化
    self.server_status_signal.connect(self.server_status_change)
    self.mcp_server_status_signal.connect(self.mcp_server_status_change)
    self.downloading_signal.connect(self.downloading_change)
    self.mitmproxy_server_status_signal.connect(self.mitmproxy_server_status_change)
    self.message_dialog_signal.connect(self.show_message_dialog)
    self.cleanup_done_signal.connect(self._on_cleanup_done)
    self.cleanup_progress_signal.connect(self._on_cleanup_progress)
    '''
    按钮事件绑定
    '''

    def catch_server_port_change(value):
      self.catch_server_port = value

    def compress_image_button_click():
      self.compress_image = not self.compress_image

    def static_download_button_click():
      self.download_static()

    def server_port_change(value):
      self.server_port = value

    def mcp_server_port_change(value):
      self.mcp_server_port = value

    def response_delay_change(value):
      self.response_delay = value

    def static_load_speed_change(value):
      self.static_load_speed = value

    # 端口号输入绑定
    self.catchServerPortSpinBox.setValue(self.catch_server_port)
    self.catchServerPortSpinBox.valueChanged.connect(catch_server_port_change)
    self.serverPortSpinBox.setValue(self.server_port)
    self.serverPortSpinBox.valueChanged.connect(server_port_change)
    self.mcpServerPortSpinBox.setValue(self.mcp_server_port)
    self.mcpServerPortSpinBox.valueChanged.connect(mcp_server_port_change)
    self.responseDelaySpinBox.setValue(self.response_delay)
    self.responseDelaySpinBox.valueChanged.connect(response_delay_change)
    self.staticLoadSpeedSpinBox.setValue(self.static_load_speed)
    self.staticLoadSpeedSpinBox.valueChanged.connect(static_load_speed_change)
    # 抓包服务按钮
    self.catchServerButton.clicked.connect(self.catch_server_button_click)
    # 压缩静态资源按钮
    self.compressCheckBox.setChecked(self.compress_image)
    self.compressCheckBox.clicked.connect(compress_image_button_click)
    self.staticDownloadButton.clicked.connect(static_download_button_click)
    # mock 服务按钮
    self.serverButton.clicked.connect(self.server_button_click)
    # MCP 服务按钮
    self.mcpServerButton.clicked.connect(self.mcp_server_button_click)

    # 选择服务的工作目录
    self.serverWorkDirLineEdit.setText(self.work_dir)
    self.serverWorkDirLineEdit.setCursorPosition(0)
    self.serverWorkDirLineEdit.setToolTip(self.work_dir)

  # 展示提示弹窗
  def show_message_dialog(self, dialog_type: str = 'critical', title: str = '', message: str = '') -> None:
    if not message:
      return

    if dialog_type == 'critical':
      QMessageBox.critical(self, title or '异常', message)
    else:
      QMessageBox.information(self, title or '提示', message)

  # 选择工作目录
  def select_work_dir(self) -> None:
    directory = QFileDialog.getExistingDirectory(
      self,
      caption='选择工作目录',
      directory=r'./',
    )
    if directory and self.check_and_create_work_files(directory):
      # 更换工作目录后，检查目录文件
      self.work_dir = directory
      self.serverWorkDirLineEdit.setText(self.work_dir)
      self.serverWorkDirLineEdit.setCursorPosition(0)
      self.serverWorkDirLineEdit.setToolTip(self.work_dir)
      # 更新工作目录历史记录
      HISTORY_CONFIG_MANAGER.set(key='work_dir', value=self.work_dir)

  # mock 服务启动状态变化
  def server_status_change(self, text: str) -> None:
    button_text: str = ''
    disabled: bool = False
    server_btn_disabled: bool = False

    if text == 'RUNNING':
      button_text = '停止服务'
      disabled = True
      server_btn_disabled = False
    elif text == 'START_WAIT':
      button_text = '正在启动...'
      disabled = True
      server_btn_disabled = True
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

    self.serverPortSpinBox.setDisabled(disabled)
    self.responseDelaySpinBox.setDisabled(disabled)
    self.staticLoadSpeedSpinBox.setDisabled(disabled)
    set_menu_item_disabled(self.file_menu, [
      {"action_name": FILE.CHANGE_WORK_DIR, "disabled": disabled},
    ])
    set_menu_item_disabled(self.edit_menu, [
      {"action_name": EDIT.SERVER_EDIT, "disabled": disabled},
    ])
    # mock 服务启动时禁止启动抓包服务
    self.catchServerButton.setDisabled(disabled)

  # 下载状态变化
  def downloading_change(self, text: str) -> None:
    # 下载中
    if text == 'DOWNLOAD':
      download_btn_disabled = False
      disabled = True
      current = self.download_detail.get('current', 0)
      total = self.download_detail.get('total', 0)
      if current and total:
        button_text = f'停止下载({current}/{total})'
      else:
        button_text = '停止下载'
    # 正在停止下载
    elif text == 'STOP_WAIT':
      download_btn_disabled = True
      disabled = True
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

    set_menu_item_disabled(self.file_menu, [
      {"action_name": FILE.CHANGE_WORK_DIR, "disabled": disabled},
    ])
    set_menu_item_disabled(self.edit_menu, [
      {"action_name": EDIT.SERVER_EDIT, "disabled": disabled},
      {"action_name": EDIT.DOWNLOAD_EDIT, "disabled": disabled},
      {"action_name": EDIT.DOWNLOAD_PROXY_EDIT, "disabled": disabled},
    ])

  # 抓包服务启动状态变化
  def mitmproxy_server_status_change(self, text: str) -> None:
    button_text: str = ''
    disabled: bool = False
    mitmproxy_btn_disabled: bool = False

    if text == 'RUNNING':
      button_text = '停止抓包服务'
      disabled = True
      mitmproxy_btn_disabled = False
    elif text == 'START_WAIT':
      button_text = '正在启动...'
      disabled = True
      mitmproxy_btn_disabled = True
    elif text == 'STOP_WAIT':
      button_text = '正在停止...'
      disabled = True
      mitmproxy_btn_disabled = True
    elif text == 'READY':
      button_text = '启动抓包服务'
      disabled = False
      mitmproxy_btn_disabled = False

    self.mitmproxy_server_status = text

    self.catchServerButton.setText(button_text)
    self.catchServerButton.setDisabled(mitmproxy_btn_disabled)

    self.catchServerPortSpinBox.setDisabled(disabled)

    set_menu_item_disabled(self.file_menu, [
      {"action_name": FILE.CHANGE_WORK_DIR, "disabled": disabled},
    ])
    set_menu_item_disabled(self.edit_menu, [
      {"action_name": EDIT.MITMPROXY_EDIT, "disabled": disabled},
      {"action_name": EDIT.MITMPROXY_DATA_EDIT, "disabled": disabled},
    ])
    # 抓包服务启动时禁止启动 mock 服务
    self.serverButton.setDisabled(disabled)
    # 抓包服务启动时禁止启动 MCP 服务
    self.mcpServerButton.setDisabled(disabled)

  # 点击 mock 服务按钮
  def server_button_click(self) -> None:
    if self.server_status in ('START_WAIT', 'STOP_WAIT'):
      return
    if self.server_status == 'READY':
      self.server_status_signal.emit('START_WAIT')
      self.start_server()
    elif self.server_status == 'RUNNING':
      self.server_status_signal.emit('STOP_WAIT')
      self.stop_server()

  # MCP 服务启动状态变化
  def mcp_server_status_change(self, text: str) -> None:
    button_text: str = ''
    disabled: bool = False

    if text == 'RUNNING':
      button_text = '停止MCP服务'
      disabled = True
    elif text == 'START_WAIT':
      button_text = '正在启动...'
      disabled = True
    elif text == 'STOP_WAIT':
      button_text = '正在停止...'
      disabled = True
    elif text == 'READY':
      button_text = '启动MCP服务'
      disabled = False

    self.mcp_server_status = text
    self.mcpServerButton.setText(button_text)
    self.mcpServerButton.setDisabled(text in ('START_WAIT', 'STOP_WAIT'))
    self.mcpServerPortSpinBox.setDisabled(disabled)
    # MCP 服务启动时禁止启动抓包服务
    self.catchServerButton.setDisabled(disabled)

  # 点击 MCP 服务按钮
  def mcp_server_button_click(self) -> None:
    if self.mcp_server_status in ('START_WAIT', 'STOP_WAIT'):
      return
    if self.mcp_server_status == 'READY':
      self.mcp_server_status_signal.emit('START_WAIT')
      self.start_mcp_server()
    elif self.mcp_server_status == 'RUNNING':
      self.mcp_server_status_signal.emit('STOP_WAIT')
      self.stop_mcp_server()

  # 点击抓包服务按钮
  def catch_server_button_click(self) -> None:
    if self.mitmproxy_server_status in ('START_WAIT', 'STOP_WAIT'):
      return
    if self.mitmproxy_server_status == 'READY':
      self.mitmproxy_server_status_signal.emit('START_WAIT')
      self.start_catch_server()
    elif self.mitmproxy_server_status == 'RUNNING':
      self.mitmproxy_server_status_signal.emit('STOP_WAIT')
      self.stop_catch_server()

  # 检查工作目录文件完整性
  def check_and_create_work_files(self, work_dir: str = DEFAULT_WORK_DIR) -> bool:
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

  # 导出静态资源
  def output_static(self) -> None:
    output_dialog = OutputStaticDialog(work_dir=self.work_dir)
    output_dialog.exec_()

  # 启动抓包服务
  @create_thread
  def start_catch_server(self) -> None:
    # 抓包服务还在运行中，跳过
    if self.mitmproxy_process is not None and self.mitmproxy_process.is_alive():
      self.mitmproxy_server_status_signal.emit('READY')
      return

    # 网络监听端口检查
    if check_local_connection('0.0.0.0', self.catch_server_port):
      self.message_dialog_signal.emit(
        'critical',
        '端口检查',
        f'{self.catch_server_port} 端口已被占用，启动抓包服务失败！',
      )
      self.mitmproxy_server_status_signal.emit('READY')
      return

    # 抓包服务启动配置
    mitmproxy_config: MitmproxyRunConfig = {
      "host": "0.0.0.0",
      "port": self.catch_server_port,
      "work_dir": self.work_dir,
      "mitmproxy_log": app_env.MITMPROXY_LOG,
    }

    # 创建跨进程停止信号 Event
    self.mitmproxy_stop_event = Event()
    # 创建跨进程就绪信号 Event（子进程 running 钩子触发后 set）
    self.mitmproxy_ready_event = Event()
    # 启动 mitmproxy 子进程
    self.mitmproxy_process = start_mitmproxy(
      share_dict=mitmproxy_config,
      ready_event=self.mitmproxy_ready_event,
      stop_event=self.mitmproxy_stop_event,
    )
    # 阻塞等待子进程就绪信号，最多等待 10 秒
    ready = self.mitmproxy_ready_event.wait(timeout=10)
    if not ready:
      print('mitmproxy 服务启动超时（10s），请检查日志...')
    self.mitmproxy_server_status_signal.emit('RUNNING')

  # 停止抓包服务（同步）
  def _stop_catch_server(self) -> None:
    # 抓包服务未运行，跳过
    if self.mitmproxy_process is None or not self.mitmproxy_process.is_alive():
      self.mitmproxy_server_status_signal.emit('READY')
      return

    # 通过 Event 通知子进程优雅关闭
    if self.mitmproxy_stop_event is not None:
      self.mitmproxy_stop_event.set()

    # 等待子进程优雅退出
    self.mitmproxy_process.join(timeout=30)

    # 超时未退出，强制终止
    if self.mitmproxy_process.is_alive():
      print('mitmproxy 子进程优雅关闭超时，执行强制终止...')
      self.mitmproxy_process.terminate()
      self.mitmproxy_process.join(timeout=3)

    # 清理引用
    self.mitmproxy_process = None
    self.mitmproxy_stop_event = None
    self.mitmproxy_ready_event = None
    self.mitmproxy_server_status_signal.emit('READY')

  # 停止抓包服务
  @create_thread
  def stop_catch_server(self) -> None:
    self._stop_catch_server()

  # 更新下载详情
  def update_download_detail(self, detail: Dict[str, Any]) -> None:
    if not isinstance(detail, dict):
      detail = {}
    self.download_detail = detail
    # 更新下下载按钮显示
    self.downloading_signal.emit(self.download_status)

  # 下载静态资源
  @create_thread
  def download_static(self) -> None:
    # 正在下载中，点击触发停止
    if self.download_status == 'DOWNLOAD':
      self.downloading_signal.emit('STOP_WAIT')
      self._download_stop_event.set()
      return

    # 中间态拦截
    if self.download_status == 'STOP_WAIT':
      return

    self.downloading_signal.emit('DOWNLOAD')
    self._download_stop_event.clear()
    # 清空下载详情数据
    self.download_detail = {}
    # 开始下载
    download_server_static(
      work_dir=self.work_dir,
      static_url_path=STATIC_DIR,
      compress=self.compress_image,
      callback=self.update_download_detail,
      stop_event=self._download_stop_event,
    )
    # 下载任务结束后切换按钮显示
    time.sleep(0.5)
    self.downloading_signal.emit('READY')
    # 清空下载详情数据
    self.download_detail = {}

  # 强制终止 mock 服务子进程并清理引用
  def _terminate_mock_process(self, reason: str, timeout: int = 3) -> None:
    if self._mock_server_process is None:
      return
    if self._mock_server_process.is_alive():
      APP_LOGGER.warning(f'{reason}，强制终止子进程！port={self.server_port}')
      self._mock_server_process.terminate()
      self._mock_server_process.join(timeout=timeout)
    self._mock_server_process = None

  # 启动mock服务
  @create_thread
  def start_server(self) -> None:
    # 网络监听端口检查
    if check_local_connection('0.0.0.0', self.server_port):
      self.message_dialog_signal.emit(
        'critical',
        '端口检查',
        f'{self.server_port} 端口已被占用，启动 mock 服务失败！',
      )
      self.server_status_signal.emit('READY')
      return

    server_config = {
      "work_dir": self.work_dir,
      "port": self.server_port,
      "response_delay": self.response_delay,
      "static_load_speed": self.static_load_speed,
    }
    server_process = Process(
      target=server_process_start,
      args=(server_config,),
      name='mock_server',
    )
    self._mock_server_process = server_process

    server_process.start()
    time.sleep(1)
    result: bool = is_local_server_running(
      port=self.server_port,
      retry=20,
      retry_condition='NOT_RUNNING',
      caller='MOCK_SERVER_START'
    )
    APP_LOGGER.info(f"点击启动 MOCK_SERVER 后检测服务当前是否运行：{result}")
    time.sleep(0.5)
    if result:
      self.server_status_signal.emit('RUNNING')
    else:
      # 启动失败，终止子进程避免孤儿进程阻止主进程退出
      self._terminate_mock_process(reason='MOCK_SERVER 启动检测失败')
      self.message_dialog_signal.emit(
        'critical',
        '启动失败',
        f'MOCK_SERVER 启动失败，请检查日志！port={self.server_port}',
      )
      self.server_status_signal.emit('READY')

  # 停止mock服务（同步）
  def _stop_server(self) -> None:
    @error_catch(log=False)
    def shutdown():
      """这个请求发送到 mock 服务后，会触发关闭服务进程，没有响应一定会报错，这里就不打印捕获错误信息了"""
      requests.get(f'http://127.0.0.1:{self.server_port}/system/shutdown')

    shutdown()
    time.sleep(1)
    result: bool = is_local_server_running(
      port=self.server_port,
      retry=20,
      retry_condition='RUNNING',
      caller='MOCK_SERVER_STOP'
    )
    APP_LOGGER.info(f"点击停止 MOCK_SERVER 后检测服务当前是否运行：{result}")
    time.sleep(0.5)
    if result:
      self.message_dialog_signal.emit(
        'critical',
        '停止失败',
        f'MOCK_SERVER 停止失败，服务仍在运行！port={self.server_port}',
      )
      self.server_status_signal.emit('RUNNING')
    else:
      # 停止成功，清理进程引用
      self._terminate_mock_process(reason='', timeout=3)
      self.server_status_signal.emit('READY')

  # 停止mock服务
  @create_thread
  def stop_server(self) -> None:
    self._stop_server()

  # 启动 MCP 服务
  @create_thread
  def start_mcp_server(self) -> None:
    # 网络监听端口检查
    if check_local_connection('0.0.0.0', self.mcp_server_port):
      self.message_dialog_signal.emit(
        'critical',
        '端口检查',
        f'{self.mcp_server_port} 端口已被占用，启动 MCP 服务失败！',
      )
      self.mcp_server_status_signal.emit('READY')
      return

    mcp_config: McpServerRunConfig = {
      "port": self.mcp_server_port,
      "work_dir": self.work_dir,
    }
    self._mcp_stop_event = Event()
    self._mcp_server_process = start_mcp_server(mcp_config, stop_event=self._mcp_stop_event)
    time.sleep(1)
    result: bool = is_local_server_running(
      port=self.mcp_server_port,
      retry=20,
      retry_condition='NOT_RUNNING',
      caller='MCP_SERVER_START',
    )
    APP_LOGGER.info(f"点击启动 MCP_SERVER 后检测服务当前是否运行：{result}")
    time.sleep(0.5)
    if result:
      self.mcp_server_status_signal.emit('RUNNING')
    else:
      # 启动失败，终止子进程避免孤儿进程
      if self._mcp_server_process is not None and self._mcp_server_process.is_alive():
        APP_LOGGER.warning(f'MCP_SERVER 启动检测失败，强制终止子进程！port={self.mcp_server_port}')
        self._mcp_server_process.terminate()
        self._mcp_server_process.join(timeout=3)
      self._mcp_server_process = None
      self.message_dialog_signal.emit(
        'critical',
        '启动失败',
        f'MCP_SERVER 启动失败，请检查日志！port={self.mcp_server_port}',
      )
      self.mcp_server_status_signal.emit('READY')

  # 停止 MCP 服务（同步）
  def _stop_mcp_server(self) -> None:
    # 设置 stop_event 通知子进程优雅关闭
    if self._mcp_stop_event is not None:
      self._mcp_stop_event.set()

    # 等待子进程退出（带超时兜底）
    if self._mcp_server_process is not None:
      self._mcp_server_process.join(timeout=5)
      if self._mcp_server_process.is_alive():
        # 优雅关闭超时，强制终止
        APP_LOGGER.warning(f'MCP_SERVER 优雅关闭超时，强制终止！port={self.mcp_server_port}')
        self._mcp_server_process.terminate()
        self._mcp_server_process.join(timeout=3)

    # 确认端口已释放
    result: bool = is_local_server_running(
      port=self.mcp_server_port,
      retry=20,
      retry_condition='RUNNING',
      caller='MCP_SERVER_STOP',
    )
    APP_LOGGER.info(f"点击停止 MCP_SERVER 后检测服务当前是否运行：{result}")
    # 清理引用
    self._mcp_stop_event = None
    self._mcp_server_process = None
    if result:
      self.message_dialog_signal.emit(
        'critical',
        '停止失败',
        f'MCP_SERVER 停止失败，服务仍在运行！port={self.mcp_server_port}',
      )
      self.mcp_server_status_signal.emit('RUNNING')
    else:
      self.mcp_server_status_signal.emit('READY')

  # 停止 MCP 服务
  @create_thread
  def stop_mcp_server(self) -> None:
    self._stop_mcp_server()

  # 停止 APP_SERVER 服务（同步）
  def _stop_app_server(self) -> None:
    # 检查 APP_SERVER 是否正常启动
    if not is_app_server_running(self.app_sever_running_data):
      return

    @error_catch(log=False)
    def shutdown():
      app_sever_port = self.app_sever_running_data.get('port', 5050)
      """这个请求发送到 APP_SERVER 服务后，会触发关闭服务进程，没有响应一定会报错，这里就不打印捕获错误信息了"""
      requests.get(f'http://127.0.0.1:{app_sever_port}/system/shutdown')

    shutdown()

  # 停止 APP_SERVER 服务
  @create_thread
  def stop_app_server(self) -> None:
    self._stop_app_server()

  # 显示退出蒙层
  def _show_exit_overlay(self) -> None:
    if self._exit_overlay is not None:
      return
    overlay = QFrame(self)
    overlay.setObjectName('exitOverlay')
    overlay.setStyleSheet('''
      #exitOverlay {
        background-color: rgba(0, 0, 0, 140);
      }
    ''')
    layout = QVBoxLayout(overlay)
    layout.setAlignment(Qt.AlignCenter)

    card = QFrame(overlay)
    card.setStyleSheet('''
      QFrame {
        background-color: rgb(255, 248, 225);
        border-radius: 10px;
        min-width: 280px;
      }
    ''')
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(30, 30, 30, 30)
    card_layout.setSpacing(16)

    tip_label = QLabel('正在关闭应用…', card)
    tip_label.setAlignment(Qt.AlignCenter)
    tip_label.setStyleSheet('font-size: 15px; color: rgb(80, 80, 80); border: none;')
    self._exit_tip_label = tip_label

    progress_bar = QProgressBar(card)
    progress_bar.setRange(0, 0)
    progress_bar.setFixedWidth(240)
    progress_bar.setTextVisible(False)
    progress_bar.setStyleSheet('''
      QProgressBar {
        border: none;
        border-radius: 4px;
        background-color: rgb(230, 230, 230);
        height: 8px;
      }
      QProgressBar::chunk {
        border-radius: 4px;
        background-color: rgb(97, 97, 97);
      }
    ''')

    card_layout.addWidget(tip_label)
    card_layout.addWidget(progress_bar, alignment=Qt.AlignCenter)
    layout.addWidget(card)

    overlay.setGeometry(self.rect())
    overlay.raise_()
    overlay.show()
    self._exit_overlay = overlay

  # 退出清理进度槽（主线程）
  def _on_cleanup_progress(self, tip: str) -> None:
    if self._exit_tip_label is not None:
      self._exit_tip_label.setText(tip)

  # 子线程中执行停止服务（阻塞逻辑不卡 UI）
  def _cleanup_in_thread(self) -> None:
    # 停止下载线程
    if self.download_status in ('DOWNLOAD', 'STOP_WAIT'):
      self.cleanup_progress_signal.emit('正在停止下载…')
      self._download_stop_event.set()
      # 等待下载线程退出循环
      time.sleep(1)
    if self.mitmproxy_server_status == 'RUNNING':
      self.cleanup_progress_signal.emit('正在清理抓包服务…')
      self._stop_catch_server()
    if self.server_status == 'RUNNING':
      self.cleanup_progress_signal.emit('正在清理 Mock 服务…')
      self._stop_server()
    elif self._mock_server_process is not None and self._mock_server_process.is_alive():
      # 启动检测失败但子进程仍在运行（孤儿进程），强制终止
      self.cleanup_progress_signal.emit('正在清理 Mock 服务…')
      self._terminate_mock_process(reason='退出清理：检测到 MOCK_SERVER 孤儿子进程仍在运行', timeout=5)
    if self.mcp_server_status == 'RUNNING':
      self.cleanup_progress_signal.emit('正在清理 MCP 服务…')
      self._stop_mcp_server()
    elif self._mcp_server_process is not None and self._mcp_server_process.is_alive():
      self.cleanup_progress_signal.emit('正在清理 MCP 服务…')
      if self._mcp_stop_event is not None:
        self._mcp_stop_event.set()
      self._mcp_server_process.join(timeout=5)
      if self._mcp_server_process.is_alive():
        self._mcp_server_process.terminate()
        self._mcp_server_process.join(timeout=3)
      self._mcp_stop_event = None
      self._mcp_server_process = None
    if is_app_server_running(self.app_sever_running_data):
      self.cleanup_progress_signal.emit('正在清理 APP 服务…')
      self._stop_app_server()
    self.cleanup_progress_signal.emit('正在关闭数据库…')
    time.sleep(0.5)
    self.cleanup_done_signal.emit()

  # 退出清理完成槽（主线程）
  def _on_cleanup_done(self) -> None:
    MockDBCache.close_all()
    if self._exit_tip_label is not None:
      self._exit_tip_label.setText('正在退出应用…')
    QApplication.quit()

  # 重写弹窗关闭事件
  def closeEvent(self, event: QCloseEvent) -> None:
    if self._exit_overlay is not None:
      event.ignore()
      return

    reply = QMessageBox.question(
      self,
      '消息',
      '确定要退出吗？',
      QMessageBox.Yes | QMessageBox.No,
      QMessageBox.No,
    )

    if reply == QMessageBox.Yes:
      event.ignore()
      self._show_exit_overlay()
      threading.Thread(target=self._cleanup_in_thread, daemon=True).start()
    else:
      event.ignore()

  # 蒙层跟随窗口大小变化
  def resizeEvent(self, event: QResizeEvent) -> None:
    super().resizeEvent(event)
    if self._exit_overlay is not None:
      self._exit_overlay.setGeometry(self.rect())
