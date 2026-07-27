# -*- coding: utf-8 -*-
import math
from typing import Dict, Union
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen


class SpinnerWidget(QWidget):
  """旋转圆环 loading 动画，纯 QPainter 绘制，无需外部资源"""

  def __init__(self, parent=None, size: int = 44, color: QColor = QColor(120, 120, 120)) -> None:
    super().__init__(parent)
    self._size = size
    self._color = color
    self._angle = 0
    self.setFixedSize(size, size)
    self._timer = QTimer(self)
    self._timer.timeout.connect(self._on_tick)

  def start(self) -> None:
    self._timer.start(40)

  def stop(self) -> None:
    self._timer.stop()

  def _on_tick(self) -> None:
    self._angle = (self._angle + 12) % 360
    self.update()

  def paintEvent(self, _event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    margin = 4
    rect = self.rect().adjusted(margin, margin, -margin, -margin)
    # 背景灰环
    painter.setPen(QPen(QColor(225, 225, 225), 4, Qt.SolidLine, Qt.RoundCap))
    painter.drawArc(rect, 0, 360 * 16)
    # 前景旋转弧（约 110°）
    painter.setPen(QPen(self._color, 4, Qt.SolidLine, Qt.RoundCap))
    painter.drawArc(rect, -self._angle * 16, 110 * 16)
    painter.end()


class WebLoadingWidget(QWidget):
  """webview 加载中占位组件：居中旋转圆环 + 文案"""

  def __init__(self, parent=None, text: str = '加载中…') -> None:
    super().__init__(parent)
    self.setStyleSheet('background-color: rgb(250, 250, 250);')
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)
    layout.setAlignment(Qt.AlignCenter)
    self._spinner = SpinnerWidget(self)
    self._spinner.start()
    tip = QLabel(text, self)
    tip.setAlignment(Qt.AlignCenter)
    tip.setStyleSheet('font-size: 14px; color: rgb(130, 130, 130); border: none; background: transparent;')
    layout.addWidget(self._spinner, alignment=Qt.AlignCenter)
    layout.addWidget(tip, alignment=Qt.AlignCenter)

  def stop(self) -> None:
    self._spinner.stop()


def get_webview_dialog_config() -> Dict[str, Union[int, float]]:
  primary_screen = QApplication.primaryScreen()
  primary_screen_size = primary_screen.size()
  primary_width = primary_screen_size.width()
  primary_height = primary_screen_size.height()
  vw = primary_width
  vh = primary_height - 240
  width = 1920
  height = 1080
  zoom = 1
  if width <= vw:
    height = min(height, vh)
    zoom = vw / width
  else:
    width = vw
    height = vh

  width = width - 240
  x0 = math.floor((primary_width - width) * 0.5)
  y0 = math.floor((primary_height - height) * 0.5)

  return {
    "x0": x0,
    "y0": y0,
    "width": width,
    "height": height,
    "zoom": zoom,
  }
