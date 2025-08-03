# -*- coding: utf-8 -*-
import os
import json

from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebChannel import QWebChannel
from lib.TInteractObject import TInteractObj
from lib.decorate import (create_thread, error_catch)
from lib.webview_lib import get_webview_dialog_config


class DownloadProxyConfigDialog(QDialog):
  def __init__(self, work_dir='.'):
    super().__init__()
    self.work_dir = work_dir
    self.webview: QWebEngineView or None = None
    self.web_channel: QWebChannel or None = None
    self.interact_obj: TInteractObj or None = None

    self.init()

  def init(self):
    self.setWindowTitle('下载代理配置')
    self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
    webview_dialog_config: dict = get_webview_dialog_config()
    x0 = webview_dialog_config.get('x0')
    y0 = webview_dialog_config.get('y0')
    width = webview_dialog_config.get('width')
    height = webview_dialog_config.get('height')
    zoom = webview_dialog_config.get('zoom')

    # 定位到屏幕中心
    self.setGeometry(x0, y0, width, height)

    def receive(message: str):
      self.receive(message)

    # 创建 QWebEngineView 实例
    webview = QWebEngineView()
    current_page = webview.page()
    interact_obj = TInteractObj()
    interact_obj.js2qt_signal.connect(receive)
    web_channel = QWebChannel(current_page)
    # 注册信号传递对象
    web_channel.registerObject('downloadProxy', interact_obj)

    self.webview = webview
    self.web_channel = web_channel
    self.interact_obj = interact_obj

    current_page.setZoomFactor(zoom)
    current_page.setWebChannel(web_channel)
    web_path = os.path.abspath('./web/apps/dataManager/index.html')
    # current_page.load(QUrl.fromLocalFile(web_path))
    current_page.load(QUrl('http://localhost:5173/apps/configEdit/index.html#/downloadProxy'))

    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(self.webview)
    self.setLayout(layout)

  @create_thread
  @error_catch(error_msg='处理web接受信息异常')
  def receive(self, message: str):
    event_dict: dict = json.loads(message)
    print(event_dict)
