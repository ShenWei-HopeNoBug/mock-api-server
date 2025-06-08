# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout, QLayout
from PyQt5.QtCore import Qt, QRect

import os
import copy
from lib.utils_lib import ConfigFileManager
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, MITMPROXY_CONFIG_PATH)
from qt_ui.mitmproxy_config_win.win_ui import Ui_Dialog
from qt_ui.list_edit_module.module import ListEditModule

from qt_ui.mitmproxy_config_win import mitmproxy_config_win_style


# 抓包配置弹窗
class MitmproxyConfigDialog(QDialog, Ui_Dialog):
  def __init__(self, work_dir=DEFAULT_WORK_DIR):
    super().__init__()
    # 当前配置文件地址
    mitmproxy_config_path = os.path.join(r'{}{}'.format(work_dir, MITMPROXY_CONFIG_PATH))
    mitmproxy_config = WORK_FILE_DICT.get('MITMPROXY_CONFIG', {})
    init_config = copy.deepcopy(mitmproxy_config.get("default", {}))
    mitmproxy_config_manager = ConfigFileManager(
      path=mitmproxy_config_path,
      config=init_config,
    )
    mitmproxy_config_manager.init(replace=False)

    # 抓包配置文件读写管理器
    self.mitmproxy_config_manager = mitmproxy_config_manager
    # http_path 编辑模组
    self.http_path_edit_weight = None
    # static_path 编辑模组
    self.static_path_edit_weight = None

    self.init_ui()
    self.add_events()

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(mitmproxy_config_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('抓包配置')

    # 列表初始化数据
    include_path = self.mitmproxy_config_manager.get_list(key='include_path')
    static_include_path = self.mitmproxy_config_manager.get_list(key='static_include_path')

    # http_path 编辑模组
    http_path_edit_weight = ListEditModule(
      self,
      init_list=include_path,
      label_text='常规http请求过滤条件：',
    )
    http_path_edit_weight.listLabel.setToolTip('常规http请求链接中如果包含配置字符串，该请求就会被抓取')

    # static_path 编辑模组
    static_path_edit_weight = ListEditModule(
      self,
      init_list=static_include_path,
      label_text='静态资源请求过滤条件：',
    )
    static_path_edit_weight.listLabel.setToolTip('静态资源请求链接中如果包含配置字符串，该请求就会被抓取')

    widget = QWidget(self)
    widget.setGeometry(QRect(10, 0, 500, 400))
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(http_path_edit_weight)
    layout.addWidget(static_path_edit_weight)
    self.http_path_edit_weight = http_path_edit_weight
    self.static_path_edit_weight = static_path_edit_weight

  def add_events(self):
    self.confirmPushButton.clicked.connect(self.confirm)

  def confirm(self):
    self.mitmproxy_config_manager.set(
      key='include_path',
      value=self.http_path_edit_weight.get_list(),
    )
    self.mitmproxy_config_manager.set(
      key='static_include_path',
      value=self.static_path_edit_weight.get_list(),
    )
    self.close()
