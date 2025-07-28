# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QWidget, QVBoxLayout, QButtonGroup
from PyQt5.QtCore import Qt, QRect

import os
import copy
from lib.utils_lib import ConfigFileManager
from qt_ui.server_config_win.win_ui import Ui_Dialog
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, MOCK_SERVER_CONFIG_PATH)
from config.enum import SERVER
from qt_ui.server_config_win.module import (FileTypeListModule, StaticRouteListModule)

from qt_ui.server_config_win import server_config_win_style

SIMPLE_MATCH_RADIO_BUTTON_ID = 1000
EXACT_MATCH_RADIO_BUTTON_ID = 1001
PARAMS_MATCH_MODE_DICT: dict = {
  str(SIMPLE_MATCH_RADIO_BUTTON_ID): SERVER.HTTP_PARAMS_SIMPLE_MATCH,
  str(EXACT_MATCH_RADIO_BUTTON_ID): SERVER.HTTP_PARAMS_EXACT_MATCH
}
MATCH_RADIO_BUTTON_ID_DICT: dict = {
  str(SERVER.HTTP_PARAMS_SIMPLE_MATCH): SIMPLE_MATCH_RADIO_BUTTON_ID,
  str(SERVER.HTTP_PARAMS_EXACT_MATCH): EXACT_MATCH_RADIO_BUTTON_ID,
}


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
    self.server_config_manager: ConfigFileManager = server_config_manager
    self.file_type_edit_weight: FileTypeListModule or None = None
    self.static_route_edit_weight: StaticRouteListModule or None = None
    self.params_match_button_group: QButtonGroup or None = None
    self.params_match_mode: int = SERVER.HTTP_PARAMS_SIMPLE_MATCH

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
    file_type_edit_weight.listLabel.setToolTip(
      '启动服务时会解析mock数据中已配置的文件类型静态资源链接，将其转换成本地可访问的链接地址',
    )

    # static_path 编辑模组
    static_route_edit_weight = StaticRouteListModule(
      self,
      init_list=static_match_route,
      label_text='动态匹配静态资源路由：',
    )
    static_route_edit_weight.listLabel.setToolTip(
      '向mock服务请求的静态资源链接中包含配置的路由，会匹配已有的静态资源文件进行返回',
    )

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
    params_match_mode: int = self.server_config_manager.get(key='http_params_match_mode')
    if params_match_mode == SERVER.HTTP_PARAMS_EXACT_MATCH:
      self.paramsExactMatchRadioButton.setChecked(True)
    else:
      self.paramsSimpleMatchRadioButton.setChecked(True)

    self.confirmPushButton.clicked.connect(self.confirm)
    params_match_button_group = QButtonGroup(self)
    self.params_match_button_group = params_match_button_group

    # 初始化选中值
    params_match_button_group.addButton(self.paramsSimpleMatchRadioButton)
    params_match_button_group.setId(self.paramsSimpleMatchRadioButton, SIMPLE_MATCH_RADIO_BUTTON_ID)
    params_match_button_group.addButton(self.paramsExactMatchRadioButton)
    params_match_button_group.setId(self.paramsExactMatchRadioButton, EXACT_MATCH_RADIO_BUTTON_ID)

    def radio_button_clicked():
      sender = self.sender()
      params_match_id = sender.checkedId()
      self.params_match_mode = PARAMS_MATCH_MODE_DICT.get(
        str(params_match_id),
        SERVER.HTTP_PARAMS_SIMPLE_MATCH,
      )

    params_match_button_group.buttonClicked.connect(radio_button_clicked)

  def confirm(self):
    self.server_config_manager.set(
      key='include_files',
      value=self.params_match_mode or SERVER.HTTP_PARAMS_SIMPLE_MATCH,
    )
    self.server_config_manager.set(
      key='include_files',
      value=self.file_type_edit_weight.get_list(),
    )
    self.server_config_manager.set(
      key='static_match_route',
      value=self.static_route_edit_weight.get_list(),
    )
    self.close()
