# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QWidget

from qt_ui.text_input_win import text_input_win_style
from qt_ui.text_input_win.win_ui import Ui_Dialog


class TextInputDialog(QDialog, Ui_Dialog):
  confirm_signal = Signal(str)

  def __init__(self, parent: Optional[QWidget] = None, text: str = '', title: str = '') -> None:
    super(TextInputDialog, self).__init__(parent)
    self.text: str = text
    self.title: str = title

    self.init_ui()
    self.add_events()

    # 初始化输入值
    self.textEdit.setText(text)

  def init_ui(self) -> None:
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(text_input_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle(self.title)

  def add_events(self) -> None:
    self.confirmPushButton.clicked.connect(self.confirm)

  def confirm(self) -> None:
    self.confirm_signal.emit(self.textEdit.toPlainText())
    self.close()
