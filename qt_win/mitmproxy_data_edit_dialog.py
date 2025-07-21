# -*- coding: utf-8 -*-
import math
import json
import os

from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebChannel import QWebChannel
from lib.TInteractObject import TInteractObj
from lib.decorate import (create_thread, error_catch)
from lib.app_lib import (
  get_mock_api_data_list,
  fix_user_api_data,
  update_user_api_data,
  add_user_api_data,
  delete_user_api_data,
)


class MitmproxyDataEditDialog(QDialog):
  def __init__(self, work_dir='.'):
    super().__init__()
    self.work_dir = work_dir
    self.webview: QWebEngineView or None = None
    self.web_channel: QWebChannel or None = None
    self.interact_obj: TInteractObj or None = None

    self.init()

  def init(self):
    self.setWindowTitle("抓包数据管理")
    self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
    primary_screen = QApplication.primaryScreen()
    primary_screen_size = primary_screen.size()
    primary_width = primary_screen_size.width()
    primary_height = primary_screen_size.height()
    vw = primary_width
    vh = primary_height - 160
    width = 1920
    height = 1080
    zoom = 1
    if width <= vw:
      height = min(height, vh)
      zoom = vw / width
    else:
      width = vw
      height = vh

    x0 = math.floor((primary_width - width) * 0.5)
    y0 = math.floor((primary_height - height) * 0.5)

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
    web_channel.registerObject('interactObj', interact_obj)

    self.webview = webview
    self.web_channel = web_channel
    self.interact_obj = interact_obj

    current_page.setZoomFactor(zoom)
    current_page.setWebChannel(web_channel)
    web_path = os.path.abspath("./web/apps/dataManager/index.html")
    current_page.load(QUrl.fromLocalFile(web_path))

    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(self.webview)
    self.setLayout(layout)

  @create_thread
  @error_catch(error_msg='处理web接受信息异常')
  def receive(self, message: str):
    event_dict: dict = json.loads(message)

    msg_type = event_dict.get('type')
    if msg_type == 'request':
      self._request(event_dict)

  @create_thread
  def send_qt2js_dict_msg(self, data: dict):
    self.interact_obj.send_qt2js_dict_msg(data)

  # 处理 web 发出的请求相关事件
  def _request(self, event: dict):
    msg_type = event.get('type')
    name = event.get('name')
    action_id = event.get('action_id')
    if msg_type != 'request':
      return

    def send_response(data: any = None):
      self.send_qt2js_dict_msg({
        "type": msg_type,
        "name": name,
        "data": data,
        "action_id": action_id or '',
      })

    # 请求所有 mock 数据
    if name == 'get_mock_data':
      # 预览数据列表
      preview_list = get_mock_api_data_list(work_dir=self.work_dir)
      send_response({
        "list": preview_list
      })
    # 尝试修复 mock 的异常数据
    elif name == 'fix_mock_data':
      success = fix_user_api_data(work_dir=self.work_dir)
      send_response(success)
    elif name == 'edit_mock_data':
      update_data = event.get('params')
      success = update_user_api_data(work_dir=self.work_dir, update_data=update_data)
      send_response(success)
    elif name == 'add_mock_data':
      add_data = event.get('params')
      success = add_user_api_data(work_dir=self.work_dir, add_data=add_data)
      send_response(success)
    elif name == 'delete_mock_data':
      params = event.get('params', {})
      delete_id = params.get('id')
      success = delete_user_api_data(work_dir=self.work_dir, delete_id=delete_id)
      send_response(success)
