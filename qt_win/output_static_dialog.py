# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox
from qt_ui.output_static_win.win_ui import Ui_Dialog

import os
from config.work_file import (DEFAULT_WORK_DIR, DOWNLOAD_DIR, OUTPUT_DIR)
from lib.download_lib import get_output_data_list, output_static_files


# 导出静态资源弹窗
class OutputStaticDialog(QDialog, Ui_Dialog):
  def __init__(self, work_dir=DEFAULT_WORK_DIR):
    super().__init__()
    self.work_dir = work_dir
    self.output_dir = r'{}{}'.format(self.work_dir, OUTPUT_DIR)
    self.selected_row = -1
    self.init()

  def init(self):
    self.setupUi(self)
    self.browseLineEdit.setText(self.output_dir)
    self.browseLineEdit.setToolTip(self.output_dir)
    self.add_events()

  def add_events(self):
    self.browsePushButton.clicked.connect(self.select_output_dir)
    self.addPushButton.clicked.connect(self.add)
    self.deletePushButton.clicked.connect(self.delete)
    self.outputPushButton.clicked.connect(self.output)
    self.downloadLogListWidget.itemClicked.connect(self.select)

  # 获取下载日志路径列表
  def get_download_log_path_list(self):
    log_path_list = []
    for index in range(self.downloadLogListWidget.count()):
      item = self.downloadLogListWidget.item(index)
      log_path_list.append(item.text())

    log_path_list = list(set(log_path_list))

    return log_path_list

  # 选择导出目录
  def select_output_dir(self):
    directory = QFileDialog.getExistingDirectory(
      self,
      caption='选择导出目录',
      directory=r'./',
    )

    if directory:
      self.browseLineEdit.setText(directory)
      self.browseLineEdit.setToolTip(directory)

  def select(self):
    self.selected_row = self.downloadLogListWidget.selectedIndexes()[0].row()

  def add(self):
    directory = os.path.abspath(r'{}{}'.format(self.work_dir, DOWNLOAD_DIR))
    result = QFileDialog.getOpenFileNames(
      self,
      caption='选择下载日志',
      directory=directory,
      filter='下载日志文件 (*.json)',
    )
    file_list = result[0]
    log_path_set = set(self.get_download_log_path_list())

    # 过滤重复日志后的待添加路径列表
    add_path_list = [file for file in file_list if not file in log_path_set]

    if not len(add_path_list):
      return

    # 添加新的链接
    self.downloadLogListWidget.addItems(add_path_list)
    # 更新显示
    self.downloadLogListWidget.scrollToBottom()

  def delete(self):
    # 没有选中项，跳过
    if self.selected_row == -1:
      return

    self.downloadLogListWidget.takeItem(self.selected_row)
    self.selected_row = -1

  def output(self):
    log_path_list = self.get_download_log_path_list()

    # 静态资源路径列表
    output_data_list = []
    for log_path in log_path_list:
      output_data_list.extend(get_output_data_list(log_path=log_path, work_dir=self.work_dir))
    if len(output_data_list):
      output_static_files(output_dir=self.output_dir, output_list=output_data_list)
      QMessageBox.information(
        self,
        '提示',
        '静态资源导出完成！'
      )
      self.close()
    else:
      QMessageBox.information(
        self,
        '提示',
        '下载日志没有可导出的静态资源！'
      )
