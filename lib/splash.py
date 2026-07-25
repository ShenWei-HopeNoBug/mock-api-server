# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QSplashScreen, QWidget
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer

import time
from typing import Callable, Optional
from lib.decorate import create_thread

splash_style = '''
  QSplashScreen{
    background-color:rgb(255, 224, 178);
    font-size:12px;
  }
'''


# 启动动画
class StartSplash(QObject):
  percent_signal: pyqtSignal = pyqtSignal(int)

  def __init__(self) -> None:
    super().__init__()
    self.splash: Optional[QSplashScreen] = QSplashScreen()
    self.percent: int = 0
    self.finished: bool = False

    self.splash.setStyleSheet(splash_style)
    self.percent_signal.connect(self._on_percent)

  def show(self) -> None:
    self.show_percent(self.percent)
    self.splash.show()
    self.start_percent_timer()

  def finish(self, win: QWidget, callback: Optional[Callable] = None) -> None:
    self.show_percent(100)
    QTimer.singleShot(800, lambda: self._do_finish(win, callback))

  def _do_finish(self, win: QWidget, callback: Optional[Callable] = None) -> None:
    if self.splash is not None:
      self.splash.finish(win)
      self.finished = True
      self.splash.deleteLater()
      self.splash = None
    if callback:
      callback()

  def show_percent(self, value: int) -> None:
    self.percent = value
    self.percent_signal.emit(value)

  def _on_percent(self, value: int) -> None:
    if self.finished or self.splash is None:
      return
    self.splash.showMessage('启动中... {}%'.format(value), Qt.AlignCenter | Qt.AlignCenter)

  @create_thread
  def start_percent_timer(self) -> None:
    while self.percent < 99:
      time.sleep(0.1)
      if self.percent >= 99 or self.finished:
        break
      self.show_percent(self.percent + 1)
