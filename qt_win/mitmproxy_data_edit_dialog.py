# -*- coding: utf-8 -*-
import json
import os
from typing import Optional

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QStackedWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtCore import Qt, QUrl, QEvent
from PyQt5.QtWebChannel import QWebChannel
from lib.TInteractObject import TInteractObj
from lib.decorate import (create_thread, error_catch)
from lib.webview_lib import get_webview_dialog_config, WebLoadingWidget
from lib.app_lib import (
  get_user_api_data_list,
  get_mitmproxy_api_data_list,
  update_user_api_data,
  add_user_api_data,
  delete_user_api_data,
  is_app_server_running,
)
from app_types.app_gui_types import AppServerRunningData
from lib.utils_lib import get_ip_address
from lib.logger_lib import APP_LOGGER


class MitmproxyDataEditDialog(QDialog):
  def __init__(self, work_dir: str = '.', app_sever_running_data: Optional[AppServerRunningData] = None) -> None:
    super().__init__()
    # 工作目录
    self.work_dir: str = work_dir
    self.webview: Optional[QWebEngineView] = None
    self.web_channel: Optional[QWebChannel] = None
    self.interact_obj: Optional[TInteractObj] = None
    self.loading_widget: Optional[WebLoadingWidget] = None
    self.app_sever_running_data: Optional[AppServerRunningData] = app_sever_running_data

    self.init()

  @error_catch(error_msg='抓包数据管理弹窗初始化异常')
  def init(self) -> None:
    self.setWindowTitle('抓包数据管理')
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

    # 禁用右键菜单
    webview.setContextMenuPolicy(Qt.CustomContextMenu)
    webview.customContextMenuRequested.connect(lambda _: None)

    current_page = webview.page()
    interact_obj = TInteractObj()
    interact_obj.js2qt_signal.connect(receive)
    web_channel = QWebChannel(current_page)
    # 注册信号传递对象
    web_channel.registerObject('dataManager', interact_obj)

    self.webview = webview
    self.web_channel = web_channel
    self.interact_obj = interact_obj

    current_page.setZoomFactor(zoom)
    current_page.setWebChannel(web_channel)

    # 离线页面路径
    web_route = '#/outputManager'
    web_base_path = '/web-v3/apps/dataManager/index.html'

    # 检查 APP_SERVER 是否正常启动
    if is_app_server_running(self.app_sever_running_data):
      app_server_port = self.app_sever_running_data.get('port', 5050)
      local_server_url = f"http://{get_ip_address()}:{app_server_port}/static{web_base_path}{web_route}"
      APP_LOGGER.info(f"[mitmproxy_data_edit_dialog]以本地服务方式加载编辑页面: {local_server_url}")
      current_page.load(QUrl(local_server_url))
    else:
      web_path = os.path.abspath(f"./appServer/static{web_base_path}")
      APP_LOGGER.info(f"[mitmproxy_data_edit_dialog]以离线文件方式加载编辑页面: {web_path}{web_route}")
      local_url = QUrl.fromLocalFile(web_path)
      local_url.setFragment(web_route.lstrip('#'))
      current_page.load(local_url)

    # 加载中占位组件
    loading_widget = WebLoadingWidget()
    self.loading_widget = loading_widget

    # QStackedWidget: 0=loading, 1=webview，页面加载完成后切换
    stack = QStackedWidget()
    stack.addWidget(loading_widget)
    stack.addWidget(self.webview)
    stack.setCurrentIndex(0)

    def _on_load_finished(ok: bool) -> None:
      if loading_widget is not None:
        loading_widget.stop()
      stack.setCurrentIndex(1)

    webview.loadFinished.connect(_on_load_finished)

    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(stack)
    self.setLayout(layout)

  @create_thread
  @error_catch(error_msg='处理web接受信息异常')
  def receive(self, message: str) -> None:
    event_dict: dict = json.loads(message)

    msg_type = event_dict.get('type')
    if msg_type == 'request':
      self._request(event_dict)

  @create_thread
  def send_qt2js_dict_msg(self, data: dict) -> None:
    self.interact_obj.send_qt2js_dict_msg(data)

  # 处理 web 发出的请求相关事件
  def _request(self, event: dict) -> None:
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

    # 请求所有 mock 数据
    if name == 'get_mock_data':
      mock_data_type = params.get('type', '')
      # 预览数据列表
      preview_list = []
      # 判断要返回的数据源
      if mock_data_type == 'USER':
        preview_list.extend(get_user_api_data_list(work_dir=self.work_dir, reverse=True))
      elif mock_data_type == 'MITMPROXY':
        preview_list.extend(get_mitmproxy_api_data_list(work_dir=self.work_dir, reverse=True))
      else:
        preview_list.extend(get_user_api_data_list(work_dir=self.work_dir, reverse=True))
        preview_list.extend(get_mitmproxy_api_data_list(work_dir=self.work_dir, reverse=True))

      send_response({"list": preview_list})
    # 编辑 mock 接口数据
    elif name == 'edit_mock_data':
      success = update_user_api_data(work_dir=self.work_dir, update_data=params)
      send_response(success)
    # 新增 mock 接口数据
    elif name == 'add_mock_data':
      success = add_user_api_data(work_dir=self.work_dir, add_data=params)
      send_response(success)
    # 删除 mock 接口数据
    elif name == 'delete_mock_data':
      delete_id = params.get('id')
      success = delete_user_api_data(work_dir=self.work_dir, delete_id=delete_id)
      send_response(success)
    # 复制 mock 接口数据
    elif name == 'copy_mock_data':
      success = add_user_api_data(work_dir=self.work_dir, add_data=params)
      send_response(success)

  def closeEvent(self, event: QEvent) -> None:
    if self.loading_widget is not None:
      self.loading_widget.stop()
    event.accept()
