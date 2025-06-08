# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QLabel
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtGui import QCursor, QDesktopServices, QFont
from PyQt5.QtCore import QUrl

from qt_ui.about_win.win_ui import Ui_Dialog
import ENV

from qt_ui.about_win import about_win_style


class LinkLabel(QLabel):
  def __init__(self, parent=None, text='', url=''):
    super().__init__(text, parent)
    self.url = url
    self.setTextInteractionFlags(Qt.TextBrowserInteraction)
    self.setCursor(QCursor(Qt.PointingHandCursor))  # 鼠标悬停时显示手形图标
    self.linkActivated.connect(self.open_link)
    self.setStyleSheet('color:#409eff')

  def mouseReleaseEvent(self, event):
    if event.button() == Qt.LeftButton:
      self.open_link()

  def open_link(self):
    QDesktopServices.openUrl(QUrl(self.url))


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
    self.gitLable = LinkLabel(
      self,
      text='https://github.com/ShenWei-HopeNoBug/mock-api-server',
      url='https://github.com/ShenWei-HopeNoBug/mock-api-server',
    )
    self.gitLable.setGeometry(QRect(80, 52, 380, 30))
    self.gitLable.setMinimumSize(QSize(0, 30))
    font = QFont()
    font.setPointSize(10)
