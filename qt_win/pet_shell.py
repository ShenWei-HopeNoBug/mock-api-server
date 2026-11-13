# -*- coding: utf-8 -*-
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu


# 桌宠窗口壳 mixin：无边框透明置顶 + 拖拽 + 右键菜单 + 屏幕角定位 + 点按/悬停钩子
# 须置于 Qt 基类之前继承（保证事件方法生效），渲染层各自继承对应 Qt 基类
class PetShellMixin:
  # 点按判定阈值（松开时位移小于该值视为点按而非拖拽）
  TAP_DISTANCE: int = 5
  # 出生位置屏幕角边距
  CORNER_MARGIN: int = 20

  def _init_pet_shell(self, on_restore: Callable[[], None], on_quit: Callable[[], None]) -> None:
    # 恢复主面板回调（菜单「打开主面板」）
    self._on_restore = on_restore
    # 退出应用回调（菜单「退出」）
    self._on_quit = on_quit
    # 左键拖拽偏移量，非拖拽状态为 None
    self._drag_offset: Optional[QPoint] = None
    # 左键按下点，用于松开时区分点按与拖拽
    self._press_pos: Optional[QPoint] = None

    # 无边框 + 置顶 + Tool（不出现在任务栏和 Alt+Tab）
    self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
    self.setAttribute(Qt.WA_TranslucentBackground)
    # 开启鼠标跟踪：无按键移动也派发 mouseMoveEvent（视线跟随需要）
    self.setMouseTracking(True)

  # 移动到主屏右下角
  def move_to_corner(self, margin: int = CORNER_MARGIN) -> None:
    screen = QApplication.primaryScreen()
    if screen is None:
      return
    geo = screen.availableGeometry()
    self.move(
      geo.right() - self.width() - margin,
      geo.bottom() - self.height() - margin,
    )

  # 左键按下记录拖拽偏移与按下点
  def mousePressEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.LeftButton:
      self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
      self._press_pos = event.globalPosition().toPoint()
    super().mousePressEvent(event)

  # 左键按住拖动窗口；非拖拽移动转发 _on_pointer_move 钩子
  def mouseMoveEvent(self, event: QMouseEvent) -> None:
    if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
      self.move(event.globalPosition().toPoint() - self._drag_offset)
    else:
      self._on_pointer_move(event.position())
    super().mouseMoveEvent(event)

  # 松开左键：位移小于阈值视为点按 → _on_pet_tap 钩子
  def mouseReleaseEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.LeftButton:
      if self._press_pos is not None:
        dist = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
        if dist < self.TAP_DISTANCE:
          self._on_pet_tap(event.position())
      self._drag_offset = None
      self._press_pos = None
    super().mouseReleaseEvent(event)

  # 右键菜单：打开主面板 / 退出
  def contextMenuEvent(self, event: QContextMenuEvent) -> None:
    menu = QMenu(self)
    open_action = menu.addAction('打开主面板')
    open_action.triggered.connect(self._on_restore)
    quit_action = menu.addAction('退出')
    quit_action.triggered.connect(self._on_quit)
    menu.exec(event.globalPos())

  # 点按钩子（未拖拽的左键点击）：子类覆写做点击反应
  def _on_pet_tap(self, pos: QPointF) -> None:
    pass

  # 非拖拽指针移动钩子：子类覆写做视线跟随
  def _on_pointer_move(self, pos: QPointF) -> None:
    pass
