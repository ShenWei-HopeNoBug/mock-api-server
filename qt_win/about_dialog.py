# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt
from qt_ui.about_win.win_ui import Ui_Dialog
import ENV

from qt_style import about_win_style

# 应用信息弹窗
class AboutDialog(QDialog, Ui_Dialog):
  def __init__(self):
    super().__init__()
    self.init_ui()

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(about_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('应用信息')
    self.versionLable.setText(ENV.VERSION)
