# -*- coding: utf-8 -*-
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtCore import pyqtSignal, QThread, QObject
from PyQt5.QtWidgets import QMessageBox, QWidget
from qt_ui.mian_window import Ui_MainWindow
from mock_server import MockServer
from multiprocessing import Queue, Process

mock_server_queue = Queue()


def server_process_start(queue):
  mock_server = MockServer()
  queue.put(mock_server)

  # 检查和下载静态资源
  # mock_server.check_static()

  # 启本地 mock 服务
  mock_server.start_server()


# app 主窗口
class MainWindow(QWidget, Ui_MainWindow):
  server_running_signal = pyqtSignal(bool)

  def __init__(self, parent=None):
    super(MainWindow, self).__init__(parent=parent)
    self.mock_server = None
    self.server_running = False
    self.server_process = None

    self.init_ui()
    self.add_events()

  def server_running_change(self, value):
    if self.server_running != value:
      self.server_running = value
      button_text = '停止服务' if value else '启动服务'
      self.serverButton.setText(button_text)

  # 初始化窗口 UI
  def init_ui(self):
    self.setupUi(self)
    self.setWindowTitle('mock server v0.0.1-bata')

  def add_events(self):
    # 监听信号变化
    self.server_running_signal.connect(self.server_running_change)
    # 按钮事件绑定
    self.serverButton.clicked.connect(self.server_button_click)

  def server_button_click(self):
    self.stop_server() if self.server_running else self.start_server()

  def start_server(self):
    if self.server_running:
      return

    self.server_process = Process(
      target=server_process_start,
      args=(mock_server_queue,),
      name='mock_server',
    )
    self.server_process.start()
    self.server_running_signal.emit(True)

  def stop_server(self):
    if not self.server_running:
      return

    mock_server = mock_server_queue.get()
    if mock_server:
      success = mock_server.stop_server()
      self.server_running_signal.emit(not success)
    else:
      self.server_running_signal.emit(False)
    self.server_process = None

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
