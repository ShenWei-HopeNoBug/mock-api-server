# -*- coding: utf-8 -*-
import json
import os
from typing import Optional

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QStackedWidget, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl, QEvent
from PyQt5.QtWebChannel import QWebChannel
from lib.TInteractObject import TInteractObj
from lib.decorate import (create_thread, error_catch)
from lib.webview_lib import get_webview_dialog_config, WebLoadingWidget, setup_devtools
from lib.app_lib import is_app_server_running
from lib.db import MockDB, MockDBCache
from app_types.app_gui_types import (
  AppServerRunningData,
  GetMockDataPageParams,
  MockDataPageResult,
  DeleteMockDataParams,
  BatchDeleteMockDataParams,
  AddMockDataParams,
  CopyMockDataParams,
)
from app_types.db_types import ApiRecord, ApiQuery
from lib.utils_lib import get_ip_address
from lib.logger_lib import APP_LOGGER
from config.enum.BIZ_CODE import (
  BIZ_SUCCESS,
  BIZ_UNKNOWN_ERROR,
  BIZ_PARAM_MISSING,
  BIZ_FILE_READ_ERROR,
  BIZ_FILE_WRITE_ERROR,
)


class MitmproxyDataEditDialog(QDialog):
  def __init__(
      self,
      parent: Optional[QWidget] = None,
      work_dir: str = '.',
      app_sever_running_data: Optional[AppServerRunningData] = None,
  ) -> None:
    super().__init__(parent)
    # 工作目录
    self.work_dir: str = work_dir
    self.webview: Optional[QWebEngineView] = None
    self.web_channel: Optional[QWebChannel] = None
    self.interact_obj: Optional[TInteractObj] = None
    self.loading_widget: Optional[WebLoadingWidget] = None
    self.app_sever_running_data: Optional[AppServerRunningData] = app_sever_running_data
    self._devtools_view: Optional[QWebEngineView] = None

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

    # F12 打开内嵌 DevTools
    self._devtools_view = setup_devtools(webview, self)

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
    params = event.get('params', {})
    if msg_type != 'request':
      return

    def send_response(data: any = None, status_code: int = BIZ_SUCCESS, status_msg: str = ''):
      self.send_qt2js_dict_msg(
        TInteractObj.build_qt_response(name, action_id, data, status_code, status_msg)
      )

    handler = self._REQUEST_HANDLERS.get(name)
    if handler is None:
      return

    try:
      result = handler(self, params)
      send_response(result)
    except KeyError as e:
      send_response(None, status_code=BIZ_PARAM_MISSING, status_msg=f'缺少必填参数: {e}')
    except FileNotFoundError as e:
      send_response(None, status_code=BIZ_FILE_READ_ERROR, status_msg=str(e))
    except PermissionError as e:
      send_response(None, status_code=BIZ_FILE_WRITE_ERROR, status_msg=str(e))
    except Exception as e:
      send_response(None, status_code=BIZ_UNKNOWN_ERROR, status_msg=str(e))

  # --- 请求 handler：只关注业务逻辑，返回数据 ---

  def _handle_get_mock_data_page(self, params: GetMockDataPageParams) -> MockDataPageResult:
    mock_data_type = params.get('type')
    page_num = params.get('page_num', 1)
    page_size = params.get('page_size', 20)
    api_type = mock_data_type if mock_data_type in ('USER', 'MITMPROXY') else None
    enabled = params.get('enabled')
    query: ApiQuery = {
      'api_type': api_type,
      'url_like': params.get('url') or None,
      'params_like': params.get('params') or None,
      'response_like': params.get('response') or None,
      'method': params.get('method') or None,
      'request_content_type': params.get('request_content_type') or None,
      'enabled': enabled if isinstance(enabled, bool) else None,
      'create_start_time': params.get('create_start_time') or None,
      'create_end_time': params.get('create_end_time') or None,
    }
    mock_db: MockDB = MockDBCache.get(self.work_dir)

    total = mock_db.get_api_count(query)
    page_list = mock_db.get_api_list_page(
      query,
      reverse=True,
      page_num=page_num,
      page_size=page_size,
    )
    return {
      "list": page_list,
      "total": total,
      "page_num": page_num,
      "page_size": page_size,
    }

  def _handle_edit_mock_data(self, params: ApiRecord) -> bool:
    mock_db: MockDB = MockDBCache.get(self.work_dir)
    return mock_db.update_api(params)

  def _handle_add_mock_data(self, params: AddMockDataParams) -> bool:
    mock_db: MockDB = MockDBCache.get(self.work_dir)
    return mock_db.insert_api({'type': 'USER', **params})

  def _handle_delete_mock_data(self, params: DeleteMockDataParams) -> bool:
    mock_db: MockDB = MockDBCache.get(self.work_dir)
    return mock_db.delete_api(params.get('id', ''))

  def _handle_batch_delete_mock_data(self, params: BatchDeleteMockDataParams) -> bool:
    mock_db: MockDB = MockDBCache.get(self.work_dir)
    mock_data_type = params.get('type')
    api_type = mock_data_type if mock_data_type in ('USER', 'MITMPROXY') else None
    enabled = params.get('enabled')
    query: ApiQuery = {
      'api_type': api_type,
      'url_like': params.get('url') or None,
      'params_like': params.get('params') or None,
      'response_like': params.get('response') or None,
      'method': params.get('method') or None,
      'request_content_type': params.get('request_content_type') or None,
      'enabled': enabled if isinstance(enabled, bool) else None,
      'create_start_time': params.get('create_start_time') or None,
      'create_end_time': params.get('create_end_time') or None,
    }
    return mock_db.batch_delete_api(query)

  def _handle_copy_mock_data(self, params: CopyMockDataParams) -> bool:
    mock_db: MockDB = MockDBCache.get(self.work_dir)
    source = mock_db.get_api_by_id(params['id'])
    if source is None:
      return False
    return mock_db.insert_api({
      'type': 'USER',
      'url': source['url'],
      'method': source['method'],
      'params': source['params'],
      'response': source['response'],
      'timeout': source.get('timeout', 0),
      'request_content_type': source.get('request_content_type', 'NONE'),
      'enabled': source.get('enabled', True),
    })

  # 请求名称 → handler 映射
  _REQUEST_HANDLERS = {
    'get_mock_data_page': _handle_get_mock_data_page,
    'edit_mock_data': _handle_edit_mock_data,
    'add_mock_data': _handle_add_mock_data,
    'delete_mock_data': _handle_delete_mock_data,
    'batch_delete_mock_data': _handle_batch_delete_mock_data,
    'copy_mock_data': _handle_copy_mock_data,
  }

  def closeEvent(self, event: QEvent) -> None:
    if self.loading_widget is not None:
      self.loading_widget.stop()
    if self._devtools_view is not None:
      self._devtools_view.close()
    event.accept()
