# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import Qt

import os
import copy
from lib.utils_lib import ConfigFileManager
from qt_ui.server_config_win.win_ui import Ui_Dialog
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, MOCK_SERVER_CONFIG_PATH)
from qt_win.text_input_dialog import TextInputDialog

from qt_ui.server_config_win import server_config_win_style


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
    self.file_type_select_row = -1
    self.static_route_select_row = -1
    self.edit_text = ''

    self.init_ui()
    self.add_events()
    self.init()

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(server_config_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('服务配置')

  def init(self):
    self.refresh_file_type_list()
    self.refresh_static_route_list()

  def add_events(self):
    self.fileTypeListWidget.itemClicked.connect(self.file_type_select)
    self.staticRouteListWidget.itemClicked.connect(self.static_route_select)

    self.addFileTypePushButton.clicked.connect(self.add_file_type)
    self.addStaticRoutePushButton.clicked.connect(self.add_static_route)

    self.editFileTypePushButton.clicked.connect(self.edit_file_type)
    self.editStaticRoutePushButton.clicked.connect(self.edit_static_route)

    self.deleteFileTypePushButton.clicked.connect(self.delete_file_type)
    self.deleteStaticRoutePushButton.clicked.connect(self.delete_static_route)

  def refresh_file_type_list(self):
    include_files = self.server_config_manager.get_list(key='include_files')
    self.fileTypeListWidget.clear()
    self.fileTypeListWidget.addItems(include_files)

  def refresh_static_route_list(self):
    static_match_route = self.server_config_manager.get_list(key='static_match_route')
    self.staticRouteListWidget.clear()
    self.staticRouteListWidget.addItems(static_match_route)

  def file_type_select(self):
    index = self.fileTypeListWidget.selectedIndexes()[0].row()
    self.file_type_select_row = index

  def static_route_select(self):
    index = self.staticRouteListWidget.selectedIndexes()[0].row()
    self.static_route_select_row = index

  # 设置编辑文本数据
  def set_edit_text(self, text: str = ''):
    # 去除左右两边的空白字符
    self.edit_text = text.strip()

  # 添加 file_type
  def add_file_type(self):
    text_input_dialog = TextInputDialog()
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()
    if len(self.edit_text):
      result = self.server_config_manager.append_list_value(
        key='include_files',
        value=self.edit_text,
      )

      if result:
        self.fileTypeListWidget.addItem(self.edit_text)
        self.fileTypeListWidget.scrollToBottom()
      else:
        QMessageBox.critical(self, '异常', '新增失败!')

    self.edit_text = ''

  # 添加 static_route
  def add_static_route(self):
    text_input_dialog = TextInputDialog()
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()
    if len(self.edit_text):
      result = self.server_config_manager.append_list_value(
        key='static_match_route',
        value=self.edit_text,
      )

      if result:
        self.staticRouteListWidget.addItem(self.edit_text)
        self.staticRouteListWidget.scrollToBottom()
      else:
        QMessageBox.critical(self, '异常', '新增失败!')

    self.edit_text = ''

  # 编辑 file_type
  def edit_file_type(self):
    if self.file_type_select_row == -1:
      return

    current_text = self.fileTypeListWidget.item(self.file_type_select_row).text()
    text_input_dialog = TextInputDialog(text=current_text)
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()
    if len(self.edit_text) and (not current_text == self.edit_text):
      result = self.server_config_manager.update_list_value(
        key='include_files',
        value=self.edit_text,
        index=self.file_type_select_row
      )

      if result:
        # 清空选区
        self.fileTypeListWidget.clearSelection()
        self.file_type_select_row = -1
        self.refresh_file_type_list()
      else:
        QMessageBox.critical(self, '异常', '更新失败!')

    self.edit_text = ''

  # 编辑 static_route
  def edit_static_route(self):
    if self.static_route_select_row == -1:
      return

    current_text = self.staticRouteListWidget.item(self.static_route_select_row).text()
    text_input_dialog = TextInputDialog(text=current_text)
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()
    if len(self.edit_text) and (not current_text == self.edit_text):
      result = self.server_config_manager.update_list_value(
        key='static_match_route',
        value=self.edit_text,
        index=self.static_route_select_row
      )

      if result:
        # 清空选区
        self.staticRouteListWidget.clearSelection()
        self.static_route_select_row = -1
        self.refresh_static_route_list()
      else:
        QMessageBox.critical(self, '异常', '更新失败!')

    self.edit_text = ''

  # 删除 file_type
  def delete_file_type(self):
    if self.file_type_select_row == -1:
      return

    result = self.server_config_manager.delete_list_value(
      key='include_files',
      index=self.file_type_select_row
    )

    if not result:
      QMessageBox.critical(self, '异常', '删除失败!')
    else:
      self.file_type_select_row = -1
      self.refresh_file_type_list()

  # 删除 static_route
  def delete_static_route(self):
    if self.static_route_select_row == -1:
      return

    result = self.server_config_manager.delete_list_value(
      key='static_match_route',
      index=self.static_route_select_row
    )

    if not result:
      QMessageBox.critical(self, '异常', '删除失败!')
    else:
      self.static_route_select_row = -1
      self.refresh_static_route_list()
