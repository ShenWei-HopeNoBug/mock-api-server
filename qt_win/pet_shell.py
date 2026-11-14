# -*- coding: utf-8 -*-
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
  QColor,
  QContextMenuEvent,
  QIcon,
  QMouseEvent,
  QPainter,
  QPen,
  QPixmap,
)
from PySide6.QtWidgets import QApplication, QMenu

# 右键菜单样式：与主面板菜单体系统一（奶黄底 + 深灰 hover 白字 + 圆角）
PET_MENU_STYLE = '''
  QMenu {
    background-color: rgb(255, 248, 225);
    border: 1px solid rgba(97, 97, 97, 60);
    border-radius: 10px;
    padding: 6px;
  }
  QMenu::item {
    padding: 6px 28px 6px 30px;
    border-radius: 6px;
    color: rgb(80, 80, 80);
    font-size: 13px;
  }
  QMenu::item:selected {
    color: white;
    background-color: rgb(97, 97, 97);
  }
  QMenu::item:disabled {
    color: rgb(160, 160, 160);
  }
  /* 禁用项 hover 不允许出现深色底块：半透明/淡色内容压深底会糊 */
  QMenu::item:disabled:selected {
    color: rgb(160, 160, 160);
    background-color: transparent;
  }
  QMenu::icon {
    padding-left: 8px;
  }
  QMenu::separator {
    height: 1px;
    background: rgba(97, 97, 97, 60);
    margin: 4px 10px;
  }
'''


# 按颜色绘制 16x16 图标位图（window=主面板窗口轮廓 / power=电源符号）
def _draw_icon_pixmap(kind: str, color: QColor) -> QPixmap:
  pixmap = QPixmap(16, 16)
  pixmap.fill(Qt.transparent)
  painter = QPainter(pixmap)
  painter.setRenderHint(QPainter.Antialiasing)
  pen = QPen(color)
  pen.setWidthF(1.5)
  painter.setPen(pen)
  painter.setBrush(Qt.NoBrush)
  if kind == 'window':
    # 外框 + 标题栏分隔线
    painter.drawRoundedRect(QRectF(2, 2.5, 12, 11), 2, 2)
    painter.drawLine(QPointF(2, 6), QPointF(14, 6))
  elif kind == 'power':
    # 电源符号：顶部竖线 + 圆弧（顶部留缺口给竖线）
    painter.drawLine(QPointF(8, 2), QPointF(8, 8))
    painter.drawArc(QRectF(3.5, 4, 9, 9), 120 * 16, 300 * 16)
  elif kind == 'kill':
    # 强制退出：交叉 X
    painter.drawLine(QPointF(4.5, 4.5), QPointF(11.5, 11.5))
    painter.drawLine(QPointF(11.5, 4.5), QPointF(4.5, 11.5))
  elif kind == 'dot':
    # 状态点：实心圆（颜色由调用方按状态给定）
    painter.setBrush(color)
    painter.drawEllipse(QRectF(4, 4, 8, 8))
  painter.end()
  return pixmap


# 菜单图标公共入口：window/power 为深灰描边 + hover/选中反白双模式；dot 为彩色状态点（不反色）
# dot 附带 Disabled 淡化位图：禁用项的状态点同步变淡，与淡色文字一致
# 非 dot 项传 color 时走彩色路线：常态彩色、hover/选中同色相提亮（保留语义色，如 kill 红色警示）
def make_pet_menu_icon(kind: str, color: Optional[QColor] = None) -> QIcon:
  if kind == 'dot' and color is not None:
    icon = QIcon(_draw_icon_pixmap('dot', color))
    # Disabled 用浅化实色（保留色相提示，避免半透明在浅底上显糊）
    icon.addPixmap(_draw_icon_pixmap('dot', color.lighter(150)), QIcon.Disabled)
    return icon
  normal = color if color is not None else QColor(97, 97, 97)
  highlight = color.lighter(140) if color is not None else QColor(255, 255, 255)
  icon = QIcon(_draw_icon_pixmap(kind, normal))
  icon.addPixmap(_draw_icon_pixmap(kind, highlight), QIcon.Active)
  icon.addPixmap(_draw_icon_pixmap(kind, highlight), QIcon.Selected)
  return icon


# 应用桌宠菜单样式：无边框/无系统阴影/透明背景（Windows 原生菜单窗需此组合 border-radius 才生效）+ 统一 QSS
def apply_pet_menu_style(menu: QMenu) -> None:
  menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
  menu.setAttribute(Qt.WA_TranslucentBackground)
  menu.setStyleSheet(PET_MENU_STYLE)


# 桌宠窗口壳 mixin：无边框透明置顶 + 拖拽 + 右键菜单 + 屏幕角定位 + 点按/悬停钩子
# 须置于 Qt 基类之前继承（保证事件方法生效），渲染层各自继承对应 Qt 基类
class PetShellMixin:
  # 点按判定阈值（松开时位移小于该值视为点按而非拖拽）
  TAP_DISTANCE: int = 5
  # 出生位置屏幕角边距
  CORNER_MARGIN: int = 20

  def _init_pet_shell(
    self,
    on_restore: Callable[[], None],
    on_quit: Callable[[], None],
    on_build_menu: Optional[Callable[[QMenu], None]] = None,
  ) -> None:
    # 恢复主面板回调（菜单「打开主面板」）
    self._on_restore = on_restore
    # 退出应用回调（菜单「退出」）
    self._on_quit = on_quit
    # 可选菜单构建钩子（主面板注入服务快捷项等，mixin 不感知内容）
    self._on_build_menu = on_build_menu
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

  # 右键菜单：打开主面板 / 退出（圆角透明窗 + 统一样式 + 图标）
  def contextMenuEvent(self, event: QContextMenuEvent) -> None:
    menu = QMenu(self)
    apply_pet_menu_style(menu)
    # 可选的服务快捷项等钩子项在前，与窗口操作项之间加分隔线
    if self._on_build_menu is not None:
      self._on_build_menu(menu)
      menu.addSeparator()
    open_action = menu.addAction(make_pet_menu_icon('window'), '打开主面板')
    open_action.triggered.connect(self._on_restore)
    quit_action = menu.addAction(make_pet_menu_icon('power'), '退出')
    quit_action.triggered.connect(self._on_quit)
    menu.exec(event.globalPos())
    # 菜单 exec 返回即弃用：deleteLater 回收（其内挂的刷新 timer 等子对象一并销毁）
    menu.deleteLater()

  # 点按钩子（未拖拽的左键点击）：子类覆写做点击反应
  def _on_pet_tap(self, pos: QPointF) -> None:
    pass

  # 非拖拽指针移动钩子：子类覆写做视线跟随
  def _on_pointer_move(self, pos: QPointF) -> None:
    pass
