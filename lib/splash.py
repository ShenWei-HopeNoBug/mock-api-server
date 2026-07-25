# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
  QWidget, QLabel, QVBoxLayout, QProgressBar, QFrame,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer

import time
from typing import Callable, Optional
from lib.decorate import create_thread

# 启动文案，按进度区间显示
STARTUP_MESSAGES = {
  0: '正在初始化应用环境…',
  20: '正在启动 APP_SERVER 服务…',
  60: '正在加载主窗口…',
  90: '即将就绪…',
  100: '启动完成',
}

# 百分比文案模板
PERCENT_TEMPLATE = ' ({percent}%)'

SPLASH_WIDTH = 360
SPLASH_HEIGHT = 160


# 启动动画
class StartSplash(QObject):
  percent_signal: pyqtSignal = pyqtSignal(int)

  def __init__(self) -> None:
    super().__init__()
    self.splash: Optional[QWidget] = None
    self.percent: int = 0
    self.finished: bool = False

    self._tip_label: Optional[QLabel] = None
    self._progress_bar: Optional[QProgressBar] = None

    self._build_ui()
    self.percent_signal.connect(self._on_percent)

  def _build_ui(self) -> None:
    win = QWidget()
    win.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    win.setAttribute(Qt.WA_TranslucentBackground)
    win.setFixedSize(SPLASH_WIDTH, SPLASH_HEIGHT)

    # 外层布局，用于居中卡片
    outer = QVBoxLayout(win)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setAlignment(Qt.AlignCenter)

    # 卡片容器，样式与退出蒙层一致
    card = QFrame(win)
    card.setStyleSheet('''
      QFrame {
        background-color: rgb(255, 248, 225);
        border-radius: 10px;
      }
    ''')
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(30, 30, 30, 30)
    card_layout.setSpacing(16)

    # 启动文案
    tip_label = QLabel('正在启动应用…', card)
    tip_label.setAlignment(Qt.AlignCenter)
    tip_label.setStyleSheet('font-size: 15px; color: rgb(80, 80, 80); border: none;')
    self._tip_label = tip_label

    # 进度条（indeterminate，循环滚动动画）
    progress_bar = QProgressBar(card)
    progress_bar.setRange(0, 0)
    progress_bar.setFixedWidth(280)
    progress_bar.setTextVisible(False)
    progress_bar.setStyleSheet('''
      QProgressBar {
        border: none;
        border-radius: 4px;
        background-color: rgb(230, 230, 230);
        height: 8px;
      }
      QProgressBar::chunk {
        border-radius: 4px;
        background-color: rgb(97, 97, 97);
      }
    ''')
    self._progress_bar = progress_bar

    card_layout.addWidget(tip_label)
    card_layout.addWidget(progress_bar, alignment=Qt.AlignCenter)
    outer.addWidget(card)

    self.splash = win

  def show(self) -> None:
    if self.splash is None:
      return
    self.show_percent(self.percent)
    self.splash.show()
    self.start_percent_timer()

  def finish(self, win: QWidget, callback: Optional[Callable] = None) -> None:
    self.show_percent(100)
    QTimer.singleShot(800, lambda: self._do_finish(win, callback))

  def _do_finish(self, win: QWidget, callback: Optional[Callable] = None) -> None:
    if self.splash is not None:
      self.splash.close()
      self.splash.deleteLater()
      self.splash = None
    self.finished = True
    if callback:
      callback()

  def show_percent(self, value: int) -> None:
    self.percent = value
    self.percent_signal.emit(value)

  def _on_percent(self, value: int) -> None:
    if self.finished or self.splash is None:
      return
    if self._tip_label is not None:
      msg = STARTUP_MESSAGES.get(value, None)
      if msg is None:
        # 找到不超过当前进度的最大 key
        keys = [k for k in STARTUP_MESSAGES if k <= value]
        msg = STARTUP_MESSAGES[max(keys)] if keys else '正在启动应用…'
      self._tip_label.setText(msg + PERCENT_TEMPLATE.format(percent=value))

  @create_thread
  def start_percent_timer(self) -> None:
    while self.percent < 99:
      time.sleep(0.1)
      if self.percent >= 99 or self.finished:
        break
      self.show_percent(self.percent + 1)
