# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget

import copy
from lib.decorate import error_catch
from qt_ui.list_edit_module.win_ui import Ui_Form
from qt_win.text_input_dialog import TextInputDialog

from qt_ui.list_edit_module import module_style


class ListEditModule(QWidget, Ui_Form):
  def __init__(self, parent=None, init_list: list = None, label_text: str = ''):
    super(ListEditModule, self).__init__(parent)
    self.parent = parent
    self.list: list = copy.deepcopy(init_list) or []
    self.label_text = label_text
    self.select_row: int = -1
    self.edit_text: str = ''

    self.init()

  # 初始化UI
  def init_ui(self):
    self.setupUi(self)
    self.setStyleSheet(module_style.window)
    self.listLabel.setText(self.label_text)

  # 绑定事件
  def add_events(self):
    def add():
      self.add()

    def edit():
      self.edit()

    def delete():
      self.delete()

    self.addPushButton.clicked.connect(add)
    self.editPushButton.clicked.connect(edit)
    self.deletePushButton.clicked.connect(delete)
    self.listWidget.itemClicked.connect(self.select)

  # 初始化
  def init(self):
    self.init_ui()
    self.add_events()
    self.refresh()

  # 刷新选中项和列表展示
  def refresh(self):
    self.listWidget.clearSelection()
    self.select_row = -1
    self.refresh_list_weight()

  # 刷新列表展示
  def refresh_list_weight(self):
    self.listWidget.clear()
    self.listWidget.addItems(self.list)

  def select(self):
    index = self.listWidget.selectedIndexes()[0].row()
    self.select_row = index

  def get_list(self):
    return copy.deepcopy(self.list)

  # 设置编辑文本数据
  def set_edit_text(self, text: str = ''):
    # 去除左右两边的空白字符
    self.edit_text = text.strip()

  # 检查编辑选项文本是否合法（预留函数）
  def check_edit_valid(
      self,
      text: str = '',
      old_text: str = '',
      is_edit: bool = False,
      current_list: list = None,
  ) -> bool:
    return True

  @error_catch(error_msg='新增失败', error_return=False)
  def add(self) -> bool:
    text_input_dialog = TextInputDialog(title='新增')
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()

    def is_valid():
      return self.check_edit_valid(
        text=self.edit_text,
        old_text='',
        is_edit=False,
        current_list=self.get_list()
      )

    # 检查编辑内容合法性
    if (
        not len(self.edit_text) or
        not is_valid()
    ):
      self.edit_text = ''
      return False

    if self.edit_text in self.list:
      return False

    self.list.append(self.edit_text)
    self.listWidget.addItem(self.edit_text)
    self.edit_text = ''
    return True

  @error_catch(error_msg='编辑失败', error_return=False)
  def edit(self):
    if self.select_row == -1:
      return False

    old_text = self.listWidget.item(self.select_row).text()
    text_input_dialog = TextInputDialog(text=old_text, title='编辑')
    text_input_dialog.confirm_signal.connect(self.set_edit_text)
    text_input_dialog.exec_()

    def is_valid():
      return self.check_edit_valid(
        text=self.edit_text,
        old_text=old_text,
        is_edit=False,
        current_list=self.get_list()
      )

    # 检查编辑内容合法性
    if (
        not len(self.edit_text) or
        not is_valid()
    ):
      self.edit_text = ''
      return False

    # 索引范围校验
    if self.select_row < 0 or self.select_row >= len(self.list):
      return False

    self.list[self.select_row] = self.edit_text
    self.edit_text = ''
    self.refresh()
    return True

  @error_catch(error_msg='删除失败', error_return=False)
  def delete(self) -> bool:
    if self.select_row == -1:
      return False

    # 索引范围校验
    if self.select_row < 0 or self.select_row >= len(self.list):
      return False

    del self.list[self.select_row]
    self.refresh()
    return True
