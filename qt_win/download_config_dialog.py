# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout, QMessageBox
from PyQt5.QtCore import Qt, QRect

import os
import re
import copy
from lib.utils_lib import ConfigFileManager
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, DOWNLOAD_CONFIG_PATH)
from qt_ui.download_config_win.win_ui import Ui_Dialog
from qt_ui.list_edit_module.module import ListEditModule

from qt_ui.download_config_win import download_config_win_style

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
    self.download_config_manager = download_config_manager
    # file_type 编辑模组
    self.file_type_edit_weight = None

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

  def confirm(self):
    self.download_config_manager.set(
      key='include_files',
      value=self.file_type_edit_weight.get_list(),
    )
    self.close()
