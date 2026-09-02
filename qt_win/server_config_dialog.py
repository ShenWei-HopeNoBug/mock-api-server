# -*- coding: utf-8 -*-
from typing import Optional

from PyQt5.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QListView
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QRect

import os
import copy
from lib.utils_lib import ConfigFileManager
from qt_ui.server_config_win.win_ui import Ui_Dialog
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, MOCK_SERVER_CONFIG_PATH)
from qt_ui.server_config_win.module import (FileTypeListModule, StaticRouteListModule)
from lib.throttle_lib import get_strategy_options

from qt_ui.server_config_win import server_config_win_style


class ServerConfigDialog(QDialog, Ui_Dialog):
  def __init__(self, work_dir: str = DEFAULT_WORK_DIR) -> None:
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
    self.file_type_edit_weight: Optional[FileTypeListModule] = None
    self.static_route_edit_weight: Optional[StaticRouteListModule] = None
    self.throttle_combo: Optional[QComboBox] = None
    self.init_ui()
    self.add_events()

  def init_ui(self) -> None:
    self.setupUi(self)
    self.setFixedSize(520, 620)
    self.setWindowOpacity(0.95)
    self.setStyleSheet(server_config_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('服务配置')

    # 确定按钮下移，避免与新增内容重叠
    self.confirmPushButton.setGeometry(QRect(430, 560, 71, 30))

    include_files = self.server_config_manager.get_list(key='include_files')
    static_match_route = self.server_config_manager.get_list(key='static_match_route')

    # http_path 编辑模组
    file_type_edit_weight = FileTypeListModule(
      self,
      init_list=include_files,
      label_text='静态资源包含文件类型(比如 .png)：',
    )
    file_type_edit_weight.setFixedHeight(200)
    file_type_edit_weight.listLabel.setToolTip(
      '启动服务时会解析mock数据中已配置的文件类型静态资源链接，将其转换成本地可访问的链接地址',
    )

    # static_path 编辑模组
    static_route_edit_weight = StaticRouteListModule(
      self,
      init_list=static_match_route,
      label_text='动态匹配静态资源路由：',
    )
    static_route_edit_weight.setFixedHeight(200)
    static_route_edit_weight.listLabel.setToolTip(
      '向mock服务请求的静态资源链接中包含配置的路由，会匹配已有的静态资源文件进行返回',
    )

    widget = QWidget(self)
    widget.setGeometry(QRect(10, 0, 500, 470))
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    # 静态资源限速策略选择
    throttle_widget = QWidget(self)
    throttle_layout = QHBoxLayout(throttle_widget)
    throttle_layout.setContentsMargins(0, 0, 0, 0)
    throttle_layout.setSpacing(8)

    throttle_label = QLabel('静态资源限速策略：')
    throttle_combo = QComboBox()
    for value, label in get_strategy_options():
      throttle_combo.addItem(label, value)

    # 使用 QListView 作为下拉视图，确保 ::item 样式生效
    list_view = QListView()
    list_view.setStyleSheet('''
      QListView {
        background-color: rgb(250, 250, 250);
        border: 1px solid skyblue;
        border-radius: 0px;
        padding: 2px;
        outline: none;
        font-size: 8pt;
      }
      QListView::item {
        min-height: 24px;
        padding: 2px 6px;
        margin: 1px 0px;
        border-radius: 4px;
      }
      QListView::item:hover {
        background-color: rgb(255, 245, 225);
      }
      QListView::item:selected {
        background-color: rgb(255, 224, 178);
        color: black;
        border-radius: 4px;
      }
    ''')
    throttle_combo.setView(list_view)

    # 通过 QFont 设置输入框字体大小
    throttle_font = QFont()
    throttle_font.setPointSize(9)
    throttle_combo.setFont(throttle_font)

    current_strategy = self.server_config_manager.get('throttle_strategy')
    idx = throttle_combo.findData(current_strategy)
    if idx >= 0:
      throttle_combo.setCurrentIndex(idx)

    throttle_combo.setToolTip(
      '选择静态资源限速策略，不同策略模拟不同的弱网传输效果'
    )

    throttle_layout.addWidget(throttle_label)
    throttle_layout.addWidget(throttle_combo, 1)
    throttle_widget.setFixedHeight(40)

    # 用外层 wrapper 给限速策略整行加上下边距
    throttle_wrapper = QWidget(self)
    throttle_wrapper_layout = QVBoxLayout(throttle_wrapper)
    throttle_wrapper_layout.setContentsMargins(12, 8, 12, 8)
    throttle_wrapper_layout.setSpacing(0)
    throttle_wrapper_layout.addWidget(throttle_widget)

    layout.addWidget(file_type_edit_weight)
    layout.addWidget(static_route_edit_weight)
    layout.addWidget(throttle_wrapper)
    self.file_type_edit_weight = file_type_edit_weight
    self.static_route_edit_weight = static_route_edit_weight
    self.throttle_combo = throttle_combo

  def add_events(self) -> None:
    self.confirmPushButton.clicked.connect(self.confirm)

  def confirm(self) -> None:
    self.server_config_manager.set(
      key='include_files',
      value=self.file_type_edit_weight.get_list(),
    )
    self.server_config_manager.set(
      key='static_match_route',
      value=self.static_route_edit_weight.get_list(),
    )
    self.server_config_manager.set(
      key='throttle_strategy',
      value=self.throttle_combo.currentData(),
    )
    self.close()
