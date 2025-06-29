# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QMessageBox, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QRect

import os
import copy
import re
from lib.utils_lib import ConfigFileManager
from qt_ui.server_config_win.win_ui import Ui_Dialog
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, MOCK_SERVER_CONFIG_PATH)
from config.route import (INNER_ROUTE_LIST)
from qt_ui.list_edit_module.module import ListEditModule

from qt_ui.server_config_win import server_config_win_style


class FileTypeListModule(ListEditModule):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def check_edit_valid(
      self,
      text: str = '',
      old_text: str = '',
      is_edit: bool = False,
      current_list: list = None,
  ):
    valid = bool(re.match(r'^\.[a-zA-Z0-9]+$', text))
    if not valid:
      QMessageBox.critical(
        self,
        '异常',
        '请输入标准的文件扩展名文本（扩展名字符可包含大小写字母和数字），如：\n .jpg, .png',
      )

    return valid


class StaticRouteListModule(ListEditModule):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def check_edit_valid(
      self,
      text: str = '',
      old_text: str = '',
      is_edit: bool = False,
      current_list: list = None,
  ) -> bool:
    valid: bool = bool(re.match(r'^/[a-zA-Z0-9_-]+$', text))
    if not valid:
      QMessageBox.critical(
        self,
        '异常',
        '请输入指定格式的路由（路由字符可包含大小写字母、数字、下划线和中划线），如：\n /test，/test2, /my_path',
      )

    inner_route_set = set(INNER_ROUTE_LIST)
    if text in inner_route_set:
      valid = False
      QMessageBox.critical(
        self,
        '异常',
        '该路由名已被应用内部服务占用，请不要使用以下路由进行命名：\n{}'.format('，'.join(INNER_ROUTE_LIST)),
      )

    return valid


class ServerConfigDialog(QDialog, Ui_Dialog):
  def __init__(self, work_dir=DEFAULT_WORK_DIR):
    super().__init__()
    # 当前配置文件地址
    server_config_path = os.path.join(r'{}{}'.format(work_dir, MOCK_SERVER_CONFIG_PATH))
    mock_server_config = WORK_FILE_DICT.get('MOCK_SERVER_CONFIG', {})
    init_config = copy.deepcopy(mock_server_config.get('default', {}))
    server_config_manager = ConfigFileManager(
      path=server_config_path,
      config=init_config,
    )
    server_config_manager.init(replace=False)

    # 服务配置文件读写管理器
    self.server_config_manager = server_config_manager
    self.file_type_edit_weight = None
    self.static_route_edit_weight = None

    self.init_ui()
    self.add_events()

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(server_config_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('服务配置')

    include_files = self.server_config_manager.get_list(key='include_files')
    static_match_route = self.server_config_manager.get_list(key='static_match_route')

    # http_path 编辑模组
    file_type_edit_weight = FileTypeListModule(
      self,
      init_list=include_files,
      label_text='静态资源包含文件类型(比如 .png)：',
    )
    file_type_edit_weight.listLabel.setToolTip('启动服务时会解析mock数据中已配置的文件类型静态资源链接，将其转换成本地可访问的链接地址')

    # static_path 编辑模组
    static_route_edit_weight = StaticRouteListModule(
      self,
      init_list=static_match_route,
      label_text='动态匹配静态资源路由：',
    )
    static_route_edit_weight.listLabel.setToolTip('向mock服务请求的静态资源链接中包含配置的路由，会匹配已有的静态资源文件进行返回')

    widget = QWidget(self)
    widget.setGeometry(QRect(10, 0, 500, 400))
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(file_type_edit_weight)
    layout.addWidget(static_route_edit_weight)
    self.file_type_edit_weight = file_type_edit_weight
    self.static_route_edit_weight = static_route_edit_weight

  def add_events(self):
    self.confirmPushButton.clicked.connect(self.confirm)

  def confirm(self):
    self.server_config_manager.set(
      key='include_files',
      value=self.file_type_edit_weight.get_list(),
    )
    self.server_config_manager.set(
      key='static_match_route',
      value=self.static_route_edit_weight.get_list(),
    )
    self.close()
