# -*- coding: utf-8 -*-
import json
import os

from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl, QEvent
from PyQt5.QtWebChannel import QWebChannel
from config.work_file import (DATA_DIR, BACKUP_DIR, USER_API_FILE_NAME)
from lib.TInteractObject import TInteractObj
from lib.decorate import (create_thread, error_catch)
from lib.webview_lib import get_webview_dialog_config
from lib.app_lib import (
  get_user_api_data_list,
  get_mitmproxy_api_data_list,
  fix_user_api_data,
  update_user_api_data,
  add_user_api_data,
  delete_user_api_data,
  is_app_server_running,
)
from lib.utils_lib import get_ip_address
from lib.backup_lib import SimpleFolderBackup


class MitmproxyDataEditDialog(QDialog):
  def __init__(self, work_dir='.', app_sever_running_data: dict = None):
    super().__init__()
    # 需要备份的源文件夹路径
    source_dir = os.path.abspath(r'{}{}'.format(work_dir, DATA_DIR))
    # 备份文件存放的目标文件夹路径
    backup_dir = os.path.abspath(r'{}{}{}'.format(work_dir, BACKUP_DIR, DATA_DIR))
    # 工作目录
    self.work_dir = work_dir
    # 备份文件实例对象
    self.simple_folder_backup: SimpleFolderBackup = SimpleFolderBackup(
      source_dir=source_dir,
      backup_dir=backup_dir,
      watch_backup_files=[f'/{USER_API_FILE_NAME}'],
    )
    self.webview: QWebEngineView or None = None
    self.web_channel: QWebChannel or None = None
    self.interact_obj: TInteractObj or None = None
    self.app_sever_running_data: dict or None = app_sever_running_data

    self.init()
    self.simple_folder_backup.watch_diff_backup()

  @error_catch(error_msg='抓包数据管理弹窗初始化异常')
  def init(self):
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

    # 检查 APP_SERVER 是否正常启动
    if is_app_server_running(self.app_sever_running_data):
      app_server_port = self.app_sever_running_data.get('port', 5050)
      current_page.load(
        QUrl(f"http://{get_ip_address()}:{app_server_port}/static/web/apps/dataManager/index.html")
      )
    else:
      web_path = os.path.abspath('./appServer/static/web/apps/dataManager/index.html')
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
    # 尝试修复 mock 的异常数据
    elif name == 'fix_mock_data':
      success = fix_user_api_data(work_dir=self.work_dir)
      send_response(success)
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

  def closeEvent(self, event: QEvent):
    # 检查文件是否变化判断是否备份文件
    self.simple_folder_backup.watch_diff_backup()
    event.accept()
