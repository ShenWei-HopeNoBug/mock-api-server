# -*- coding: utf-8 -*-
import math
from typing import Optional
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QPaintEvent


class SpinnerWidget(QWidget):
  """旋转圆环 loading 动画，纯 QPainter 绘制，无需外部资源"""

  def __init__(self, parent: Optional[QWidget] = None, size: int = 44, color: QColor = QColor(120, 120, 120)) -> None:
    """初始化旋转圆环
    :param parent: 父组件
    :param size: 控件固定尺寸（正方形，像素）
    :param color: 前景旋转弧颜色
    """
    super().__init__(parent)
    self._size: int = size
    self._color: QColor = color
    self._angle: int = 0
    self.setFixedSize(size, size)
    # 定时器驱动旋转，每 40ms 触发一次 _on_tick
    self._timer: QTimer = QTimer(self)
    self._timer.timeout.connect(self._on_tick)

  def start(self) -> None:
    """启动旋转动画"""
    self._timer.start(40)

  def stop(self) -> None:
    """停止旋转动画"""
    self._timer.stop()

  def _on_tick(self) -> None:
    """定时器槽函数：每次递增 12° 并触发重绘，360° 取模实现循环"""
    self._angle = (self._angle + 12) % 360
    self.update()

  def paintEvent(self, _event: QPaintEvent) -> None:
    """绘制圆环：先画完整背景灰环，再叠加前景旋转弧
    Qt drawArc 角度单位为 1/16 度，故需乘以 16
    """
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    margin = 4
    rect = self.rect().adjusted(margin, margin, -margin, -margin)
    # 背景灰环（完整 360°）
    painter.setPen(QPen(QColor(225, 225, 225), 4, Qt.SolidLine, Qt.RoundCap))
    painter.drawArc(rect, 0, 360 * 16)
    # 前景旋转弧（约 110°），起始角度随 _angle 变化产生旋转效果
    painter.setPen(QPen(self._color, 4, Qt.SolidLine, Qt.RoundCap))
    painter.drawArc(rect, -self._angle * 16, 110 * 16)
    painter.end()


class WebLoadingWidget(QWidget):
  """webview 加载中占位组件：居中旋转圆环 + 文案"""

  def __init__(self, parent: Optional[QWidget] = None, text: str = '加载中…') -> None:
    super().__init__(parent)
    self.setStyleSheet('background-color: rgb(250, 250, 250);')
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)
    layout.setAlignment(Qt.AlignCenter)
    self._spinner: SpinnerWidget = SpinnerWidget(self)
    self._spinner.start()
    tip: QLabel = QLabel(text, self)
    tip.setAlignment(Qt.AlignCenter)
    tip.setStyleSheet('font-size: 14px; color: rgb(130, 130, 130); border: none; background: transparent;')
    layout.addWidget(self._spinner, alignment=Qt.AlignCenter)
    layout.addWidget(tip, alignment=Qt.AlignCenter)

  def stop(self) -> None:
    self._spinner.stop()


def get_webview_dialog_config() -> dict:
  primary_screen = QApplication.primaryScreen()
  primary_screen_size = primary_screen.size()
  primary_width: int = primary_screen_size.width()
  primary_height: int = primary_screen_size.height()
  vw: int = primary_width
  vh: int = primary_height - 240
  width: int = 1920
  height: int = 1080
  zoom: float = 1
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
