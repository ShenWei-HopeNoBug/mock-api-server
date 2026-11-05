# -*- coding: utf-8 -*-
import copy
import os
from typing import ClassVar, Dict, List, Optional

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QStackedWidget, QVBoxLayout, QWidget

from app_types.app_gui_types import AppServerRunningData
from app_types.download_types import (
  DownloadProxyItem,
  GetDownloadProxyListResult,
  UpdateDownloadProxyParams,
)
from app_types.qt_bridge_types import EventHandler, QtBridgeEvent, RequestHandler
from config.work_file import DEFAULT_WORK_DIR, DOWNLOAD_CONFIG_PATH, WORK_FILE_DICT
from lib.app_lib import is_app_server_running
from lib.bridge_lib import BridgeDispatcher
from lib.logger_lib import APP_LOGGER
from lib.TInteractObject import TInteractObj
from lib.utils_lib import ConfigFileManager
from lib.webview_lib import WebLoadingWidget, get_webview_dialog_config, setup_devtools


class DownloadProxyConfigDialog(QDialog):
  close_signal: Signal = Signal()

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
    # 强引用持有 dispatcher：bound method 若被 GC 会断开信号连接，前端请求全部超时
    self._bridge: Optional[BridgeDispatcher[DownloadProxyConfigDialog]] = None

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

    # 创建 QWebEngineView 实例
    webview = QWebEngineView()
    # 隐藏期间 RWHV 仍按 widget 几何产帧，先撑到弹窗尺寸：
    # 否则首帧按初始小尺寸产出，loadFinished 切栈时会先闪一帧「小画面→全屏」
    webview.resize(self.contentsRect().size())

    # 禁用右键菜单
    webview.setContextMenuPolicy(Qt.CustomContextMenu)
    webview.customContextMenuRequested.connect(lambda _: None)

    current_page = webview.page()
    interact_obj = TInteractObj()
    self._bridge = BridgeDispatcher(
      send=interact_obj.send_qt2js_dict_msg,
      request_handlers=self._REQUEST_HANDLERS,
      event_handlers=self._EVENT_HANDLERS,
      handler_context=self,
      tag='downloadProxy',
    )
    interact_obj.js2qt_signal.connect(self._bridge.dispatch)
    web_channel = QWebChannel(current_page)
    # 注册信号传递对象
    web_channel.registerObject('downloadProxy', interact_obj)

    self.webview = webview
    self.web_channel = web_channel
    self.interact_obj = interact_obj

    current_page.setZoomFactor(zoom)
    current_page.setWebChannel(web_channel)
    # 底色与页面一致，避免隐藏→显示切换时 underlay 颜色差异
    current_page.setBackgroundColor(Qt.white)
    # Qt6 剪贴板双重门控：ClipboardReadWrite 授权供 navigator.clipboard.writeText，
    # JavascriptCanAccessClipboard 供前端 execCommand('copy') 回退路径
    webview.settings().setAttribute(
      QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
      True,
    )

    def _on_feature_permission_requested(
      security_origin: QUrl,
      feature: QWebEnginePage.Feature,
    ) -> None:
      if feature == QWebEnginePage.Feature.ClipboardReadWrite:
        current_page.setFeaturePermission(
          security_origin,
          feature,
          QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
        )

    current_page.featurePermissionRequested.connect(_on_feature_permission_requested)

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

  def showEvent(self, event: QEvent) -> None:
    super().showEvent(event)
    # 栈内隐藏期间仍标记页面可见：webview 持续产帧，loadFinished 切换时无首帧空窗黑闪
    QTimer.singleShot(0, lambda: self.webview.page().setVisible(True))

  def closeEvent(self, event: QEvent) -> None:
    if self._bridge is not None:
      self._bridge.shutdown()
    if self.loading_widget is not None:
      self.loading_widget.stop()
    if self._devtools_view is not None:
      self._devtools_view.close()
    event.accept()

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

  _REQUEST_HANDLERS: ClassVar[Dict[str, RequestHandler['DownloadProxyConfigDialog']]] = {
    '/download_proxy/list': _handle_get_download_proxy_list,
    '/download_proxy/update': _handle_update_download_proxy,
  }

  # 事件名称 → handler 映射（单向事件，无需回包）
  _EVENT_HANDLERS: ClassVar[Dict[str, EventHandler['DownloadProxyConfigDialog']]] = {
    'download_proxy.close_requested': _handle_close_requested,
  }
