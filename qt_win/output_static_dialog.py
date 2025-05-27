# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QFileDialog
from qt_ui.output_static_win.win_ui import Ui_Dialog


# 导出静态资源弹窗
class OutputStaticDialog(QDialog, Ui_Dialog):
  def __init__(self):
    super().__init__()
    self.selected_row = -1
    self.init()

  def init(self):
    self.setupUi(self)
    self.add_events()

  def add_events(self):
    self.addPushButton.clicked.connect(self.add)
    self.deletePushButton.clicked.connect(self.delete)
    self.outputPushButton.clicked.connect(self.output)
    self.downloadLogListWidget.itemClicked.connect(self.select)

  def select(self):
    self.selected_row = self.downloadLogListWidget.selectedIndexes()[0].row()

  def add(self):
    result = QFileDialog.getOpenFileNames(
      self,
      caption='选择下载日志',
      directory=r'./',
      filter='下载日志文件 (*.json)',
    )
    file_list = result[0]
    if not len(file_list):
      return

    # 添加新的链接
    self.downloadLogListWidget.addItems(file_list)
    # 更新显示
    self.downloadLogListWidget.scrollToBottom()

  def delete(self):
    # 没有选中项，跳过
    if self.selected_row == -1:
      return

    self.downloadLogListWidget.takeItem(self.selected_row)
    self.selected_row = -1

  def output(self):
    log_list = []
    for index in range(self.downloadLogListWidget.count()):
      item = self.downloadLogListWidget.item(index)
      log_list.append(item.text())
    print('output', log_list)
    self.close()
