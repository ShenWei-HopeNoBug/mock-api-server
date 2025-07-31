# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout
from PyQt5.QtCore import Qt, QRect

import os
import copy
from config.default import DEFAULT_DOWNLOAD_CONNECT_TIMEOUT
from config.enum import DOWNLOAD
from lib.utils_lib import (ConfigFileManager, limit_num_range)
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, DOWNLOAD_CONFIG_PATH)
from qt_ui.download_config_win.win_ui import Ui_Dialog

from qt_ui.download_config_win import download_config_win_style
from qt_ui.download_config_win.module import FileTypeListModule


# 抓包配置弹窗
class DownloadConfigDialog(QDialog, Ui_Dialog):
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

    # 抓包配置文件读写管理器
    self.download_config_manager: ConfigFileManager = download_config_manager
    # file_type 编辑模组
    self.file_type_edit_weight: FileTypeListModule or None = None
    self.download_timeout: int = DEFAULT_DOWNLOAD_CONNECT_TIMEOUT

    self.init_ui()
    self.add_events()

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(download_config_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('下载配置')

    # 初始化超时时间
    download_timeout: int = self.download_config_manager.get(key='download_timeout') or DEFAULT_DOWNLOAD_CONNECT_TIMEOUT
    init_timeout: int = limit_num_range(
      num=download_timeout,
      min_limit=DOWNLOAD.MIN_CONNECT_TIMEOUT,
      max_limit=DOWNLOAD.MAX_CONNECT_TIMEOUT,
    )
    self.download_timeout = init_timeout
    self.timeoutSpinBox.setMinimum(DOWNLOAD.MIN_CONNECT_TIMEOUT)
    self.timeoutSpinBox.setMaximum(DOWNLOAD.MAX_CONNECT_TIMEOUT)
    self.timeoutSpinBox.setValue(init_timeout)

    # 列表初始化数据
    include_path = self.download_config_manager.get_list(key='include_files')

    # http_path 编辑模组
    file_type_edit_weight = FileTypeListModule(
      self,
      init_list=include_path,
      label_text='下载静态资源包含文件类型(比如 .png)：',
    )

    widget = QWidget(self)
    widget.setGeometry(QRect(10, 0, 500, 200))
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(file_type_edit_weight)
    self.file_type_edit_weight = file_type_edit_weight

  def add_events(self):
    self.confirmPushButton.clicked.connect(self.confirm)

    def timeout_input_change(value):
      self.download_timeout = value

    self.timeoutSpinBox.valueChanged.connect(timeout_input_change)

  def confirm(self):
    self.download_config_manager.set(
      key='download_timeout',
      value=self.download_timeout or DEFAULT_DOWNLOAD_CONNECT_TIMEOUT,
    )
    self.download_config_manager.set(
      key='include_files',
      value=self.file_type_edit_weight.get_list(),
    )
    self.close()
