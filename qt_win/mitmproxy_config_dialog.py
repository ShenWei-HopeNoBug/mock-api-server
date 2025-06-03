# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt
from qt_ui.mitmproxy_config_win.win_ui import Ui_Dialog

from qt_ui.mitmproxy_config_win import mitmproxy_config_win_style


# 抓包配置弹窗
class MitmproxyConfigDialog(QDialog, Ui_Dialog):
  def __init__(self):
    super().__init__()
    self.init_ui()

  def init_ui(self):
    self.setupUi(self)
    self.setFixedSize(self.width(), self.height())
    self.setWindowOpacity(0.95)
    self.setStyleSheet(mitmproxy_config_win_style.window)
    # 隐藏帮助问号按钮
    self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    self.setWindowTitle('抓包配置')
