# -*- coding: utf-8 -*-
"""
Live2D 接入隔离验证脚本（tools/live2d_spike.py）

验证项（对应 docs/plans/v0_1_5/desktop-pet/desktop-pet-live2d-plan.md §3）：
1. QOpenGLWidget 顶层窗 + 无边框透明置顶 → 模型渲染 + 背景真透明
2. 透明区逐像素点击穿透（人工：窗口盖住桌面图标，点模型轮廓外看下层是否响应）
3. --in-process-gpu 环境共存（复刻 main.py 环境变量）
4. PyInstaller --collect-all live2d 打包冒烟（另验）

操作：左键拖拽移动；点按（位移<5px 且命中 Body）播放 TapBody 动作；
     鼠标移动视线跟随；Esc 或右键菜单退出。
"""
import os
import sys

# 复刻 main.py 环境：--in-process-gpu 规避 Qt6 WebEngine GPU 闪帧（QTBUG-142355 同类）
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--in-process-gpu')

import live2d
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QMouseEvent, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication, QMenu

# 模型路径与主链路同源：走 app_env 的 system/pet_model.json 配置加载（相对路径以 work_dir 为基，模型放 server/pets/）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app_env import load_pet_model_config  # noqa: E402

_cfg = load_pet_model_config()
MODEL_JSON = _cfg['model_json']
WIN_W, WIN_H = _cfg['window_w'], _cfg['window_h']
FPS = 30


class SpikeWin(QOpenGLWidget):
  def __init__(self) -> None:
    super().__init__()
    self.model = None
    self._drag_offset = None
    self._press_pos = None

    self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
    self.setAttribute(Qt.WA_TranslucentBackground)
    # 关键坑位：QOpenGLWidget 在透明顶层窗中需关闭自动填充背景（live2d-py issue #30）
    self.setAutoFillBackground(False)
    self.resize(WIN_W, WIN_H)

    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    self.setFormat(fmt)

    # 移到主屏右下角
    geo = QApplication.primaryScreen().availableGeometry()
    self.move(geo.right() - WIN_W - 20, geo.bottom() - WIN_H - 20)

    self._timer = QTimer(self)
    self._timer.timeout.connect(self.update)
    self._timer.start(int(1000 / FPS))

  def initializeGL(self) -> None:
    live2d.glInit()
    self.model = live2d.Model()
    self.model.LoadModelJson(MODEL_JSON)
    self.model.Resize(self.width(), self.height())
    # 待机动作循环：空闲时持续随机 Idle 组动作
    self.model.StartRandomMotion('Idle', priority=1)

  def resizeGL(self, w: int, h: int) -> None:
    if self.model:
      self.model.Resize(w, h)

  def paintGL(self) -> None:
    if not self.model:
      return
    live2d.clearBuffer()
    self.model.Update()
    self.model.Draw()
    # 待机动作播完后自动补下一段，保持模型"活着"
    if self.model.IsMotionFinished():
      self.model.StartRandomMotion('Idle', priority=1)

  # 左键拖拽移动窗口
  def mousePressEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.LeftButton:
      self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
      self._press_pos = event.globalPosition().toPoint()
    super().mousePressEvent(event)

  def mouseMoveEvent(self, event: QMouseEvent) -> None:
    if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
      self.move(event.globalPosition().toPoint() - self._drag_offset)
    elif self.model:
      # 非拖拽移动：视线跟随（坐标需乘 devicePixelRatio，高 DPI 已知坑）
      scale = self.devicePixelRatioF()
      self.model.Drag(event.position().x() * scale, event.position().y() * scale)
    super().mouseMoveEvent(event)

  # 松开：位移 <5px 视为点按，命中 Body 播 TapBody，否则播任意动作
  def mouseReleaseEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.LeftButton:
      if self._press_pos is not None and self.model:
        dist = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
        if dist < 5:
          scale = self.devicePixelRatioF()
          x, y = event.position().x() * scale, event.position().y() * scale
          if self.model.IsAreaHit('Body', x, y):
            self.model.StartRandomMotion('TapBody')
          else:
            self.model.StartRandomMotion()
      self._drag_offset = None
      self._press_pos = None
    super().mouseReleaseEvent(event)

  def contextMenuEvent(self, event) -> None:
    menu = QMenu(self)
    quit_action = menu.addAction('退出 spike')
    quit_action.triggered.connect(self.close)
    menu.exec(event.globalPos())

  def keyPressEvent(self, event) -> None:
    if event.key() == Qt.Key_Escape:
      self.close()


def main() -> None:
  QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
  QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
  live2d.init()
  app = QApplication(sys.argv)
  app.setStyle('windowsvista')

  win = SpikeWin()
  win.show()

  print('=' * 60)
  print('Live2D spike 验证项：')
  print(' 1. 模型渲染 + 背景透明（看立绘四周是否为桌面）')
  print(' 2. 透明区点穿（拖到桌面图标上，点轮廓外看下层是否响应）')
  print(' 3. --in-process-gpu 共存（观察是否闪帧/黑屏）')
  print(' 4. 打包另验：pyinstaller --collect-all live2d')
  print('操作：拖拽移动 / 点按播放动作 / 移动视线跟随 / Esc 或右键退出')
  print('=' * 60)

  rc = app.exec()
  live2d.dispose()
  sys.exit(rc)


if __name__ == '__main__':
  main()
