# -*- coding: utf-8 -*-
from typing import Callable, Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPaintEvent, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

import app_env
from qt_win.pet_shell import PetShellMixin


# 桌宠悬浮窗（降级占位渲染层）：无边框透明置顶，绘制应用图标
# 左键拖拽移动；恢复主面板/退出统一走右键菜单（不做双击恢复，避免后续 Live2D 互动频繁点击误触）
class DesktopPetWindow(PetShellMixin, QWidget):
  # 窗口边长
  WINDOW_SIZE: int = 100
  # 图标绘制直径（居中绘制，四周留透明区）
  ICON_SIZE: int = 64

  def __init__(
    self,
    on_restore: Callable[[], None],
    on_quit: Callable[[], None],
    on_build_menu: Optional[Callable] = None,
  ) -> None:
    super().__init__()
    self._init_pet_shell(on_restore, on_quit, on_build_menu)
    self.setFixedSize(self.WINDOW_SIZE, self.WINDOW_SIZE)
    # 应用图标位图（.ico 含多尺寸，按目标大小取最优档；加载失败 paint 时走暖色圆兜底防隐形窗）
    self._icon_pixmap: QPixmap = QIcon(app_env.APP_ICON).pixmap(QSize(self.ICON_SIZE, self.ICON_SIZE))
    # 命中区域裁成图标方形：四周 10px 透明边在 OS 层面点穿（静态形状 setMask 即可）
    self.setMask(QRegion(self._icon_rect()))

  # 图标绘制区域（窗口内居中）
  def _icon_rect(self) -> QRect:
    margin: int = (self.WINDOW_SIZE - self.ICON_SIZE) // 2
    return QRect(margin, margin, self.ICON_SIZE, self.ICON_SIZE)

  # 绘制应用图标；图标缺失时兜底画暖色圆（否则窗口全透明不可见）
  def paintEvent(self, _event: QPaintEvent) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    rect = self._icon_rect()
    if not self._icon_pixmap.isNull():
      painter.drawPixmap(rect, self._icon_pixmap)
    else:
      painter.setPen(Qt.NoPen)
      painter.setBrush(QColor(250, 140, 60))
      painter.drawEllipse(rect)
    painter.end()
