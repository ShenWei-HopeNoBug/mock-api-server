# -*- coding: utf-8 -*-
import os
import json
import copy
from collections import OrderedDict
from threading import Lock
from typing import List, Optional

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QStackedWidget, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl, QEvent, pyqtSignal
from PyQt5.QtWebChannel import QWebChannel
from lib.TInteractObject import TInteractObj
from lib.decorate import (create_thread, error_catch)
from lib.webview_lib import get_webview_dialog_config, WebLoadingWidget, setup_devtools
from lib.utils_lib import (ConfigFileManager)
from lib.app_lib import is_app_server_running
from lib.biz_error_lib import resolve_biz_error
from app_types.app_gui_types import AppServerRunningData
from app_types.download_types import (
  DownloadProxyItem,
  GetDownloadProxyListResult,
  UpdateDownloadProxyParams,
)
from app_types.qt_bridge_types import QtBridgeEvent, QtBridgeIncomingMessage, QtBridgeRequest
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, DOWNLOAD_CONFIG_PATH)
from lib.logger_lib import APP_LOGGER
from config.enum.BIZ_CODE import (
  BIZ_SUCCESS,
  BIZ_PARAM_INVALID,
)


class DownloadProxyConfigDialog(QDialog):
  close_signal: pyqtSignal = pyqtSignal()

  def __init__(
      self,
      parent: Optional[QWidget] = None,
      work_dir: str = DEFAULT_WORK_DIR,
      app_sever_running_data: Optional[AppServerRunningData] = None,
  ) -> None:
    super().__init__(parent)
    # 当前配置文件地址
    download_config_path = os.path.join(r'{}{}'.format(work_dir, DOWNLOAD_CONFIG_PATH))
    download_config = WORK_FILE_DICT.get('DOWNLOAD_CONFIG', {})
    init_config = copy.deepcopy(download_config.get("default", {}))
    download_config_manager = ConfigFileManager(
      path=download_config_path,
      config=init_config,
    )
    download_config_manager.init(replace=False)

    self.work_dir: str = work_dir
    self.webview: Optional[QWebEngineView] = None
    self.web_channel: Optional[QWebChannel] = None
    self.interact_obj: Optional[TInteractObj] = None
    self.loading_widget: Optional[WebLoadingWidget] = None
    self.download_config_manager: ConfigFileManager = download_config_manager
    self.app_sever_running_data: Optional[AppServerRunningData] = app_sever_running_data
    self._devtools_view: Optional[QWebEngineView] = None
    self._seen_event_ids = OrderedDict()
    self._event_lock = Lock()

    self.init()

  def init(self) -> None:
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

    # 禁用右键菜单
    webview.setContextMenuPolicy(Qt.CustomContextMenu)
    webview.customContextMenuRequested.connect(lambda _: None)

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

    # F12 打开内嵌 DevTools
    self._devtools_view = setup_devtools(webview, self)

    # 离线页面路径
    web_route = '#/downloadProxy'
    web_base_path = '/web-v3/apps/configEdit/index.html'

    # 检查 APP_SERVER 是否正常启动
    if is_app_server_running(self.app_sever_running_data):
      app_server_port = self.app_sever_running_data.get('port', 5050)
      local_server_url = f"http://127.0.0.1:{app_server_port}/static{web_base_path}{web_route}"
      APP_LOGGER.info(f"[download_proxy_config_dialog]以本地服务方式加载编辑页面: {local_server_url}")
      current_page.load(QUrl(local_server_url))
    else:
      web_path = os.path.abspath(f"./appServer/static{web_base_path}")
      APP_LOGGER.info(f"[download_proxy_config_dialog]以离线文件方式加载编辑页面: {web_path}{web_route}")
      local_url = QUrl.fromLocalFile(web_path)
      local_url.setFragment(web_route.lstrip('#'))
      current_page.load(local_url)

    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(stack)
    self.setLayout(layout)

    def close_dialog():
      self.close()

    self.close_signal.connect(close_dialog)

  def closeEvent(self, event: QEvent) -> None:
    if self.loading_widget is not None:
      self.loading_widget.stop()
    if self._devtools_view is not None:
      self._devtools_view.close()
    event.accept()

  @create_thread
  def send_qt2js_dict_msg(self, data: dict) -> None:
    self.interact_obj.send_qt2js_dict_msg(data)

  @create_thread
  @error_catch(error_msg='处理web接受信息异常')
  def receive(self, message: str) -> None:
    incoming: QtBridgeIncomingMessage = json.loads(message)
    if incoming.get('type') == 'request':
      self._request(incoming)
    elif incoming.get('type') == 'event':
      self._event(incoming)

  def _request(self, event: QtBridgeRequest) -> None:
    if event.get('type') != 'request':
      return

    name = event.get('name', '')
    action_id = event.get('action_id', '')
    params = event.get('params', {})

    def send_response(
        data: any = None,
        status_code: int = BIZ_SUCCESS,
        status_msg: str = '',
    ) -> None:
      self.send_qt2js_dict_msg(
        TInteractObj.build_qt_response(name, action_id, data, status_code, status_msg)
      )

    handler = self._REQUEST_HANDLERS.get(name)
    if handler is None:
      send_response(
        None,
        status_code=BIZ_PARAM_INVALID,
        status_msg=f'不支持的请求路径: {name}',
      )
      return

    try:
      result = handler(self, params)
    except Exception as e:
      status_code, status_msg = resolve_biz_error(e)
      send_response(None, status_code=status_code, status_msg=status_msg)
      return

    send_response(result)

  # 处理 web 发出的单向事件（无需回包）
  def _event(self, event: QtBridgeEvent) -> None:
    # 忽略类型不匹配或缺少去重标识的消息
    if event.get('type') != 'event':
      return
    name = event.get('name')
    action_id = event.get('action_id')
    if not isinstance(name, str) or not isinstance(action_id, str) or not action_id:
      return
    handler = self._EVENT_HANDLERS.get(name)
    if handler is None:
      return

    # receive 在独立线程执行，检查与记录需加锁；只保留最近 256 个事件标识
    key = (name, action_id)
    with self._event_lock:
      if key in self._seen_event_ids:
        return
      self._seen_event_ids[key] = None
      if len(self._seen_event_ids) > 256:
        self._seen_event_ids.popitem(last=False)

    try:
      handler(self, event)
    except Exception:
      # 处理失败不计入已完成事件，允许相同 action_id 重试
      with self._event_lock:
        self._seen_event_ids.pop(key, None)
      raise

  def _handle_close_requested(self, _event: QtBridgeEvent) -> None:
    self.close_signal.emit()

  def _handle_get_download_proxy_list(self, _params: dict) -> GetDownloadProxyListResult:
    download_proxy_list: List[DownloadProxyItem] = self.download_config_manager.get_list(key='download_proxy_list')
    return {"list": download_proxy_list}

  def _handle_update_download_proxy(self, params: UpdateDownloadProxyParams) -> None:
    if not isinstance(params, dict):
      raise ValueError('请求参数必须是对象')
    if 'download_proxy_list' not in params:
      raise KeyError('download_proxy_list')
    download_proxy_list = params['download_proxy_list']
    if not isinstance(download_proxy_list, list) or not all(
        isinstance(item, dict) for item in download_proxy_list
    ):
      raise ValueError('download_proxy_list 必须是代理配置对象数组')
    if not self.download_config_manager.set('download_proxy_list', download_proxy_list):
      raise RuntimeError('下载代理配置保存失败，请查看应用日志')

  _REQUEST_HANDLERS = {
    '/download_proxy/list': _handle_get_download_proxy_list,
    '/download_proxy/update': _handle_update_download_proxy,
  }

  # 事件名称 → handler 映射（单向事件，无需回包）
  _EVENT_HANDLERS = {
    'download_proxy.close_requested': _handle_close_requested,
  }
