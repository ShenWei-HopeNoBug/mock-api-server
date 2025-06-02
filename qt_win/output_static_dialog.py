# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal
from qt_ui.output_static_win.win_ui import Ui_Dialog

import os
from config.work_file import (DEFAULT_WORK_DIR, DOWNLOAD_DIR, OUTPUT_DIR)
from lib.download_lib import (get_output_data_list, output_static_files)
from lib.decorate import create_thread

from qt_style import output_static_win_style


# 导出静态资源弹窗
class OutputStaticDialog(QDialog, Ui_Dialog):
  # 导出状态信号
  output_status_signal = pyqtSignal(str)
  # 提示弹窗信号
  message_dialog_signal = pyqtSignal(str, str, str)

  def __init__(self, work_dir=DEFAULT_WORK_DIR):
    super().__init__()
    self.work_dir = os.path.abspath(work_dir)
    self.output_dir = os.path.abspath(r'{}{}'.format(self.work_dir, OUTPUT_DIR))
    self.selected_row = -1
    # -----------------
    # 导出状态
    # READY：待运行
    # DOING：运行中
    # DISABLED：禁用状态
    # -----------------
    self.output_status = 'DISABLED'
    self.init_ui()
    self.init()

  def init(self):
    self.browseLineEdit.setText(self.output_dir)
    self.browseLineEdit.setCursorPosition(0)
    self.browseLineEdit.setToolTip(self.output_dir)
    self.add_events()

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(output_static_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('导出静态资源')

  def add_events(self):
    # 点击导出按钮
    def output_button_click():
      reply = QMessageBox.question(
        self,
        '消息',
        '确认要开始导出静态资源？',
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
      )

      if reply == QMessageBox.Yes:
        self.output()

    def clear_btn_click():
      reply = QMessageBox.question(
        self,
        '消息',
        '确认要清空列表数据？',
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
      )

      if reply == QMessageBox.Yes:
        self.clear_list_widget()

    self.browsePushButton.clicked.connect(self.select_output_dir)
    self.clearPushButton.clicked.connect(clear_btn_click)
    self.addPushButton.clicked.connect(self.add)
    self.deletePushButton.clicked.connect(self.delete)
    self.outputPushButton.clicked.connect(output_button_click)
    self.downloadLogListWidget.itemClicked.connect(self.select)

    self.output_status_signal.connect(self.output_status_change)
    self.message_dialog_signal.connect(self.show_message_dialog)

    # 数据初始化
    self.clearPushButton.setDisabled(True)
    self.output_status_signal.emit(self.output_status)
    self.set_select_row(-1)

  # 展示提示弹窗
  def show_message_dialog(self, dialog_type='critical', title='', message: str = ''):
    if not message:
      return

    if dialog_type == 'critical':
      QMessageBox.critical(self, title or '提示', message)
    else:
      QMessageBox.information(self, title or '异常', message)

  # 设置选中索引
  def set_select_row(self, value: int):
    self.selected_row = value
    self.deletePushButton.setDisabled(value == -1)

  # 获取下载日志路径列表
  def get_download_log_path_list(self):
    log_path_list = []
    for index in range(self.downloadLogListWidget.count()):
      item = self.downloadLogListWidget.item(index)
      log_path_list.append(item.text())

    log_path_list = list(set(log_path_list))

    return log_path_list

  # 导出状态变化
  def output_status_change(self, text: str):
    button_text: str = ''
    disabled: bool = False
    output_btn_disabled: bool = False
    if text == 'DOING':
      button_text = '导出中...'
      disabled = True
      output_btn_disabled = True
    elif text == 'DISABLED':
      button_text = '导出'
      disabled = False
      output_btn_disabled = True
    else:
      button_text = '导出'
      disabled = False
      output_btn_disabled = False

    self.output_status = text
    self.addPushButton.setDisabled(disabled)
    self.deletePushButton.setDisabled(disabled or self.selected_row == -1)
    self.outputPushButton.setDisabled(output_btn_disabled)
    self.outputPushButton.setText(button_text)

  # 清空列表
  def clear_list_widget(self):
    self.downloadLogListWidget.clear()
    self.downloadLogListWidget.clearSelection()
    self.set_select_row(-1)
    self.output_status_signal.emit('DISABLED')
    self.clearPushButton.setDisabled(True)

  # 选择导出目录
  def select_output_dir(self):
    directory = QFileDialog.getExistingDirectory(
      self,
      caption='选择导出目录',
      directory=r'./',
    )

    if directory:
      self.browseLineEdit.setText(directory)
      self.browseLineEdit.setCursorPosition(0)
      self.browseLineEdit.setToolTip(directory)
      self.output_dir = directory

  # 选中选项
  def select(self):
    index = self.downloadLogListWidget.selectedIndexes()[0].row()
    self.set_select_row(index)

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
    self.output_status_signal.emit('READY')
    self.clearPushButton.setDisabled(False)

  def delete(self):
    # 没有选中项，跳过
    if self.selected_row == -1:
      return

    self.downloadLogListWidget.takeItem(self.selected_row)
    self.set_select_row(-1)
    log_path_list = self.get_download_log_path_list()
    self.downloadLogListWidget.clearSelection()
    if not len(log_path_list):
      self.output_status_signal.emit('DISABLED')
      self.clearPushButton.setDisabled(True)

  # 导出静态资源
  @create_thread
  def output(self):
    # 非待导出状态，跳过
    if not self.output_status == 'READY':
      return

    self.output_status_signal.emit('DOING')
    log_path_list = self.get_download_log_path_list()

    # 静态资源路径列表
    output_data_list = []
    for log_path in log_path_list:
      output_data_list.extend(get_output_data_list(log_path=log_path, work_dir=self.work_dir))
    if len(output_data_list):
      output_static_files(output_dir=self.output_dir, output_list=output_data_list)
      self.message_dialog_signal.emit('information', '提示', '导出静态资源完成！')
      # 清空列表
      self.clear_list_widget()
      os.startfile(os.path.abspath(self.output_dir))
    else:
      self.output_status_signal.emit('READY')
      self.message_dialog_signal.emit('critical', '异常', '解析下载日志文件后，当前没有可导出的静态资源！')
