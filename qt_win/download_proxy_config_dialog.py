# -*- coding: utf-8 -*-
import os
import json
import copy

from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtWebChannel import QWebChannel
from lib.TInteractObject import TInteractObj
from lib.decorate import (create_thread, error_catch)
from lib.webview_lib import get_webview_dialog_config
from lib.utils_lib import (ConfigFileManager)
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, DOWNLOAD_CONFIG_PATH)


class DownloadProxyConfigDialog(QDialog):
  close_signal: pyqtSignal = pyqtSignal()

  def __init__(self, work_dir=DEFAULT_WORK_DIR):
    super().__init__()
    # 当前配置文件地址
    download_config_path = os.path.join(r'{}{}'.format(work_dir, DOWNLOAD_CONFIG_PATH))
    download_config = WORK_FILE_DICT.get('DOWNLOAD_CONFIG', {})
    init_config = copy.deepcopy(download_config.get("default", {}))
    download_config_manager = ConfigFileManager(
      path=download_config_path,
      config=init_config,
    )
    download_config_manager.init(replace=False)

    self.work_dir = work_dir
    self.webview: QWebEngineView or None = None
    self.web_channel: QWebChannel or None = None
    self.interact_obj: TInteractObj or None = None
    self.download_config_manager: ConfigFileManager = download_config_manager

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

    def close_dialog():
      self.close()

    self.close_signal.connect(close_dialog)

  @create_thread
  def send_qt2js_dict_msg(self, data: dict):
    self.interact_obj.send_qt2js_dict_msg(data)

  @create_thread
  @error_catch(error_msg='处理web接受信息异常')
  def receive(self, message: str):
    event_dict: dict = json.loads(message)
    msg_type = event_dict.get('type')
    if msg_type == 'request':
      self._request(event_dict)

  def _request(self, event: dict):
    msg_type = event.get('type')
    name = event.get('name')
    action_id = event.get('action_id')
    extra = event.get('extra', {})
    params = event.get('params', {})
    if msg_type != 'request':
      return

    def send_response(data: any = None):
      self.send_qt2js_dict_msg({
        "type": msg_type,
        "name": name,
        "data": data,
        "action_id": action_id or '',
        "extra": extra,
      })

    # 获取下载代理配置列表
    if name == 'get_download_proxy':
      download_proxy_list = self.download_config_manager.get_list(key='download_proxy_list')
      send_response({"list": download_proxy_list})
    # 更新下载代理配置列表
    elif name == 'update_download_proxy':
      download_proxy_list = params.get('download_proxy_list', [])
      self.download_config_manager.set(
        'download_proxy_list',
        download_proxy_list,
      )
      self.close_signal.emit()
