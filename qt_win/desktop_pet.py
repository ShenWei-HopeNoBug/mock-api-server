# -*- coding: utf-8 -*-
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import (
  QColor,
  QContextMenuEvent,
  QMouseEvent,
  QPainter,
  QPaintEvent,
  QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget


# 桌宠悬浮窗：无边框透明置顶占位圆球
# 左键拖拽移动；恢复主面板/退出统一走右键菜单（不做双击恢复，避免后续 Live2D 互动频繁点击误触）
class DesktopPetWindow(QWidget):
  # 窗口边长
  WINDOW_SIZE: int = 100
  # 球体直径（居中绘制，四周留透明区，配合 WA_TranslucentBackground 验证透明区点击穿透）
  BALL_SIZE: int = 80

  def __init__(self, on_restore: Callable[[], None], on_quit: Callable[[], None]) -> None:
    super().__init__()
    # 恢复主面板回调（双击/菜单「打开主面板」）
    self._on_restore = on_restore
    # 退出应用回调（菜单「退出」）
    self._on_quit = on_quit
    # 左键拖拽偏移量，非拖拽状态为 None
    self._drag_offset: Optional[QPoint] = None

    # 无边框 + 置顶 + Tool（不出现在任务栏和 Alt+Tab）
    self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
    self.setAttribute(Qt.WA_TranslucentBackground)
    self.setFixedSize(self.WINDOW_SIZE, self.WINDOW_SIZE)

  # 球体绘制区域（窗口内居中）
  def _ball_rect(self) -> QRect:
    margin: int = (self.WINDOW_SIZE - self.BALL_SIZE) // 2
    return QRect(margin, margin, self.BALL_SIZE, self.BALL_SIZE)

  # 移动到主屏右下角
  def move_to_corner(self, margin: int = 20) -> None:
    screen = QApplication.primaryScreen()
    if screen is None:
      return
    geo = screen.availableGeometry()
    self.move(
      geo.right() - self.width() - margin,
      geo.bottom() - self.height() - margin,
    )

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

  # 左键按下记录拖拽偏移
  def mousePressEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.LeftButton:
      self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    super().mousePressEvent(event)

  # 左键按住拖动窗口
  def mouseMoveEvent(self, event: QMouseEvent) -> None:
    if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
      self.move(event.globalPosition().toPoint() - self._drag_offset)
    super().mouseMoveEvent(event)

  # 松开左键结束拖拽
  def mouseReleaseEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.LeftButton:
      self._drag_offset = None
    super().mouseReleaseEvent(event)

  # 右键菜单：打开主面板 / 退出
  def contextMenuEvent(self, event: QContextMenuEvent) -> None:
    menu = QMenu(self)
    open_action = menu.addAction('打开主面板')
    open_action.triggered.connect(self._on_restore)
    quit_action = menu.addAction('退出')
    quit_action.triggered.connect(self._on_quit)
    menu.exec(event.globalPos())
