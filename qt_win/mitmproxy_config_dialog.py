# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import Qt

import os
from lib.utils_lib import ConfigFileManager
from config.work_file import (DEFAULT_WORK_DIR, WORK_FILE_DICT, MITMPROXY_CONFIG_PATH)
from qt_win.text_input_dialog import TextInputDialog
from qt_ui.mitmproxy_config_win.win_ui import Ui_Dialog

from qt_ui.mitmproxy_config_win import mitmproxy_config_win_style


# 抓包配置弹窗
class MitmproxyConfigDialog(QDialog, Ui_Dialog):
  def __init__(self, work_dir=DEFAULT_WORK_DIR):
    super().__init__()
    # 当前配置文件地址
    mitmproxy_config_path = os.path.join(r'{}{}'.format(work_dir, MITMPROXY_CONFIG_PATH))
    init_config = WORK_FILE_DICT.get('MITMPROXY_CONFIG')
    init_config['path'] = mitmproxy_config_path
    mitmproxy_config_manager = ConfigFileManager(
      path=mitmproxy_config_path,
      config=init_config,
    )
    mitmproxy_config_manager.init(replace=False)

    # 抓包配置文件读写管理器
    self.mitmproxy_config_manager = mitmproxy_config_manager
    # http_path 列表选中行
    self.http_path_select_row: int = -1
    # static_path 列表选中行
    self.static_path_select_row: int = -1
    self.edit_text = ''

    self.init_ui()
    self.add_events()
    self.init()

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(mitmproxy_config_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('抓包配置')
    self.httpPathLabel.setToolTip('常规http请求链接中如果包含配置字符串，该请求就会被抓取')
    self.staticPathLabel.setToolTip('静态资源请求链接中如果包含配置字符串，该请求就会被抓取')

  def init(self):
    self.refresh_http_path_list()
    self.refresh_static_path_list()

  def add_events(self):
    self.httpPathListWidget.itemClicked.connect(self.http_path_select)
    self.staticPathListWidget.itemClicked.connect(self.static_path_select)

    self.addHttpPathPushButton.clicked.connect(self.add_http_path)
    self.addStaticPathPushButton.clicked.connect(self.add_static_path)

    self.editHttpPathPushButton.clicked.connect(self.edit_http_path)
    self.editStaticPathPushButton.clicked.connect(self.edit_static_path)

    self.deleteHttpPathPushButton.clicked.connect(self.delete_http_path)
    self.deleteStaticPathPushButton.clicked.connect(self.delete_static_path)

  # 刷新 http_path 列表
  def refresh_http_path_list(self):
    include_path = self.mitmproxy_config_manager.get_list(key='include_path')
    self.httpPathListWidget.clear()
    self.httpPathListWidget.addItems(include_path)

  # 刷新 static_path 列表
  def refresh_static_path_list(self):
    static_include_path = self.mitmproxy_config_manager.get_list(key='static_include_path')
    self.staticPathListWidget.clear()
    self.staticPathListWidget.addItems(static_include_path)

  # 选择 http_path
  def http_path_select(self):
    index = self.httpPathListWidget.selectedIndexes()[0].row()
    self.http_path_select_row = index

  # 选择 static_path
  def static_path_select(self):
    index = self.staticPathListWidget.selectedIndexes()[0].row()
    self.static_path_select_row = index

  # 设置编辑文本数据
  def set_edit_text(self, text: str = ''):
    # 去除左右两边的空白字符
    self.edit_text = text.strip()

  # 添加 http_path
  def add_http_path(self):
    text_input_dialog = TextInputDialog()
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()
    if len(self.edit_text):
      result = self.mitmproxy_config_manager.append_list_value(
        key='include_path',
        value=self.edit_text,
      )

      if result:
        self.httpPathListWidget.addItem(self.edit_text)
        self.httpPathListWidget.scrollToBottom()
      else:
        QMessageBox.critical(self, '异常', '新增失败!')

    self.edit_text = ''

  # 添加 static_path
  def add_static_path(self):
    text_input_dialog = TextInputDialog()
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()
    if len(self.edit_text):
      result = self.mitmproxy_config_manager.append_list_value(
        key='static_include_path',
        value=self.edit_text,
      )

      if result:
        self.staticPathListWidget.addItem(self.edit_text)
        self.staticPathListWidget.scrollToBottom()
      else:
        QMessageBox.critical(self, '异常', '新增失败!')

    self.edit_text = ''

  # 编辑 http_path
  def edit_http_path(self):
    if self.http_path_select_row == -1:
      return

    current_text = self.httpPathListWidget.item(self.http_path_select_row).text()
    text_input_dialog = TextInputDialog(text=current_text)
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()
    if len(self.edit_text) and (not current_text == self.edit_text):
      result = self.mitmproxy_config_manager.update_list_value(
        key='include_path',
        value=self.edit_text,
        index=self.http_path_select_row
      )

      if result:
        # 清空选区
        self.httpPathListWidget.clearSelection()
        self.http_path_select_row = -1
        self.refresh_http_path_list()
      else:
        QMessageBox.critical(self, '异常', '更新失败!')

    self.edit_text = ''

  # 编辑 static_path
  def edit_static_path(self):
    if self.static_path_select_row == -1:
      return

    current_text = self.staticPathListWidget.item(self.static_path_select_row).text()
    text_input_dialog = TextInputDialog(text=current_text)
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()
    if len(self.edit_text) and (not current_text == self.edit_text):
      result = self.mitmproxy_config_manager.update_list_value(
        key='static_include_path',
        value=self.edit_text,
        index=self.static_path_select_row
      )

      if result:
        # 清空选区
        self.staticPathListWidget.clearSelection()
        self.static_path_select_row = -1
        self.refresh_static_path_list()
      else:
        QMessageBox.critical(self, '异常', '更新失败!')

    self.edit_text = ''

  # 删除 http_path
  def delete_http_path(self):
    if self.http_path_select_row == -1:
      return

    result = self.mitmproxy_config_manager.delete_list_value(
      key='include_path',
      index=self.http_path_select_row
    )

    if not result:
      QMessageBox.critical(self, '异常', '删除失败!')
    else:
      self.http_path_select_row = -1
      self.refresh_http_path_list()

  # 删除 static_path
  def delete_static_path(self):
    if self.static_path_select_row == -1:
      return

    result = self.mitmproxy_config_manager.delete_list_value(
      key='static_include_path',
      index=self.static_path_select_row
    )

    if not result:
      QMessageBox.critical(self, '异常', '删除失败!')
    else:
      self.static_path_select_row = -1
      self.refresh_static_path_list()
