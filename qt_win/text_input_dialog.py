# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt, pyqtSignal

from qt_ui.text_input_win.win_ui import Ui_Dialog

from qt_ui.text_input_win import text_input_win_style


class TextInputDialog(QDialog, Ui_Dialog):
  confirm_signal = pyqtSignal(str)

  def __init__(self, parent = None, text='', title=''):
    super(TextInputDialog, self).__init__(parent)
    self.text = text
    self.title = title

    self.init_ui()
    self.add_events()

    # 初始化输入值
    self.textEdit.setText(text)

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(text_input_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle(self.title)

  def add_events(self):
    self.confirmPushButton.clicked.connect(self.confirm)

  def confirm(self):
    self.confirm_signal.emit(self.textEdit.toPlainText())
    self.close()
