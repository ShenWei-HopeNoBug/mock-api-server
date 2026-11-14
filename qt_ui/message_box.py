# -*- coding: utf-8 -*-
# 暖调消息弹窗统一入口：自绘图标 + 中文按钮文本
# 原生标准图标与英文 Yes/No 是"纯 Windows 风格"的主要来源；静态方法内部建 box 无法替换图标，故统一走 helper
# 背景/文字/按钮样式由 main.py 挂到 QApplication 的 MESSAGE_BOX 片段统一渲染
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMessageBox, QWidget

from config.theme import qc

# 弹窗类型 -> (色板 token, 图标字形)
_ICON_SPEC = {
  'info': ('ACCENT', 'i'),
  'error': ('ICON_DANGER', '!'),
  'question': ('ACCENT_DEEP', '?'),
}


# 字形矢量笔画（48px 画布）：不依赖字体渲染，任何环境（含 offscreen）产出一致
def _draw_glyph(painter: QPainter, glyph: str) -> None:
  pen = QPen(qc('WHITE'), 5, Qt.SolidLine, Qt.RoundCap)
  painter.setPen(pen)
  if glyph == '?':
    # 上弧自右下开口逆时针绕顶收至左下，接竖笔与圆点
    painter.drawArc(QRectF(12, 6, 24, 22), 330 * 16, 260 * 16)
    painter.drawLine(QPointF(24, 26), QPointF(24, 33))
    painter.setPen(Qt.NoPen)
    painter.setBrush(qc('WHITE'))
    painter.drawEllipse(QPointF(24, 40), 3.2, 3.2)
  elif glyph == 'i':
    painter.setPen(Qt.NoPen)
    painter.setBrush(qc('WHITE'))
    painter.drawEllipse(QPointF(24, 10), 3.2, 3.2)
    painter.setPen(pen)
    painter.drawLine(QPointF(24, 17), QPointF(24, 38))
  else:
    painter.drawLine(QPointF(24, 9), QPointF(24, 31))
    painter.setPen(Qt.NoPen)
    painter.setBrush(qc('WHITE'))
    painter.drawEllipse(QPointF(24, 39), 3.2, 3.2)


# 自绘消息图标：实心圆底 + 居中白色矢量字形，48px 对齐 QMessageBox 标准图标量级
def _icon_pixmap(kind: str) -> QPixmap:
  color_name, glyph = _ICON_SPEC[kind]
  pixmap = QPixmap(48, 48)
  pixmap.fill(Qt.transparent)
  painter = QPainter(pixmap)
  painter.setRenderHint(QPainter.Antialiasing)
  painter.setPen(Qt.NoPen)
  painter.setBrush(qc(color_name))
  painter.drawEllipse(QRectF(2.0, 2.0, 44.0, 44.0))
  _draw_glyph(painter, glyph)
  painter.end()
  return pixmap


def _build(parent: Optional[QWidget], kind: str, title: str, text: str) -> QMessageBox:
  box = QMessageBox(parent)
  box.setWindowTitle(title)
  box.setText(text)
  box.setIconPixmap(_icon_pixmap(kind))
  return box


def msg_info(parent: Optional[QWidget], title: str, text: str) -> None:
  box = _build(parent, 'info', title, text)
  box.addButton('确定', QMessageBox.AcceptRole)
  box.exec()


def msg_error(parent: Optional[QWidget], title: str, text: str) -> None:
  box = _build(parent, 'error', title, text)
  box.addButton('确定', QMessageBox.AcceptRole)
  box.exec()


# 询问确认：返回 True=确定；默认焦点留"取消"（与原 QMessageBox.question default=No 语义一致，NoRole 键位天然吃 Esc）
def msg_question(parent: Optional[QWidget], title: str, text: str) -> bool:
  box = _build(parent, 'question', title, text)
  yes_btn = box.addButton('确定', QMessageBox.YesRole)
  no_btn = box.addButton('取消', QMessageBox.NoRole)
  box.setDefaultButton(no_btn)
  box.exec()
  return box.clickedButton() is yes_btn
