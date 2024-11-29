# -*- coding: utf-8 -*-
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import (
  QMessageBox,
  QWidget,
)


# app 主窗口
class MainWindow(QWidget):
  def __init__(self):
    super().__init__(None)
    self.initUI()

  # 初始化窗口 UI
  def initUI(self):
    self.setWindowTitle('mock server v0.0.1-bata')

  def closeEvent(self, event: QCloseEvent):
    reply = QMessageBox.question(
      self,
      '消息',
      '确定要退出吗？',
      QMessageBox.Yes | QMessageBox.No,
      QMessageBox.No,
    )

    if reply == QMessageBox.Yes:
      event.accept()
    else:
      event.ignore()
