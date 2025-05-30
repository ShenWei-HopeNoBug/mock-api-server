# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtCore import Qt

import time
from lib.decorate import create_thread

# 启动动画
class StartSplash:
  def __init__(self):
    self.splash = QSplashScreen()
    self.percent = 0
    self.finished = False

  def show(self):
    self.splash.show()
    self.show_percent(self.percent)
    self.start_percent_timer()

  def finish(self, win):
    self.show_percent(100)
    time.sleep(0.8)
    self.splash.finish(win)
    self.finished = True
    self.splash.deleteLater()
    self.splash = None

  def show_percent(self, value: int):
    self.percent = value
    if self.finished:
      return

    self.splash.showMessage('启动中... {}%'.format(self.percent), Qt.AlignCenter | Qt.AlignCenter)

  @create_thread
  def start_percent_timer(self):
    while self.percent < 99:
      time.sleep(0.1)
      if self.percent >= 99 or self.finished:
        break
      self.show_percent(self.percent + 1)
