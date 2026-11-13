# -*- coding: utf-8 -*-
from typing import Callable

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QRadialGradient
from PySide6.QtWidgets import QWidget

from qt_win.pet_shell import PetShellMixin


# 桌宠悬浮窗（占位圆球渲染层）：无边框透明置顶小球
# 左键拖拽移动；恢复主面板/退出统一走右键菜单（不做双击恢复，避免后续 Live2D 互动频繁点击误触）
class DesktopPetWindow(PetShellMixin, QWidget):
  # 窗口边长
  WINDOW_SIZE: int = 100
  # 球体直径（居中绘制，四周留透明区，配合 WA_TranslucentBackground 验证透明区点击穿透）
  BALL_SIZE: int = 80

  def __init__(self, on_restore: Callable[[], None], on_quit: Callable[[], None]) -> None:
    super().__init__()
    self._init_pet_shell(on_restore, on_quit)
    self.setFixedSize(self.WINDOW_SIZE, self.WINDOW_SIZE)

  # 球体绘制区域（窗口内居中）
  def _ball_rect(self) -> QRect:
    margin: int = (self.WINDOW_SIZE - self.BALL_SIZE) // 2
    return QRect(margin, margin, self.BALL_SIZE, self.BALL_SIZE)

  # 绘制占位圆球（径向渐变球体 + 眼睛，透明区不绘制任何像素）
  def paintEvent(self, _event: QPaintEvent) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)

    rect = self._ball_rect()
    center = rect.center()

    # 球体：光源在左上的径向渐变
    gradient = QRadialGradient(QPointF(center.x() - 18, center.y() - 18), self.BALL_SIZE * 0.8)
    gradient.setColorAt(0, QColor(255, 205, 130))
    gradient.setColorAt(1, QColor(250, 140, 60))
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawEllipse(rect)

    # 眼睛
    painter.setBrush(QColor(90, 55, 30))
    eye_r: int = 5
    eye_y: int = center.y() - 6
    painter.drawEllipse(QPointF(center.x() - 13, eye_y), eye_r, eye_r)
    painter.drawEllipse(QPointF(center.x() + 13, eye_y), eye_r, eye_r)

    painter.end()
