# -*- coding: utf-8 -*-
import os
from typing import Callable, Optional

import live2d
from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication

from qt_win.pet_shell import PetShellMixin

# live2d 进程级初始化是否完成（延迟到首个桌宠窗口创建时执行）
_live2d_ready: bool = False


# live2d 全局初始化（进程内一次），并把 dispose 挂到应用退出；失败返回 False 供调用方降级
def ensure_live2d_init() -> bool:
  global _live2d_ready
  if _live2d_ready:
    return True
  try:
    live2d.init()
    app = QApplication.instance()
    if app is not None:
      app.aboutToQuit.connect(live2d.dispose)
    _live2d_ready = True
    return True
  except Exception:
    return False


# Live2D 渲染层桌宠窗口：与 live2d-py 官方示例同构，QOpenGLWidget 直接作为顶层窗
class Live2DPetWindow(PetShellMixin, QOpenGLWidget):
  # 立绘窗口尺寸
  WINDOW_W: int = 200
  WINDOW_H: int = 300
  # 渲染帧率（桌宠不需要 60fps，省 CPU）
  FPS: int = 30

  def __init__(self, model_json: str, on_restore: Callable[[], None], on_quit: Callable[[], None]) -> None:
    super().__init__()
    if not os.path.exists(model_json):
      raise FileNotFoundError(f'Live2D 模型文件不存在：{model_json}')
    if not ensure_live2d_init():
      raise RuntimeError('live2d init failed')

    self._model_json: str = model_json
    self.model: Optional[live2d.Model] = None
    # GL 初始化失败标志：initializeGL 在 show() 时才执行，由调用方 show 后检查降级
    self.init_failed: bool = False

    self._init_pet_shell(on_restore, on_quit)
    # 关键坑位：QOpenGLWidget 在透明顶层窗中需关闭自动填充背景（live2d-py issue #30）
    self.setAutoFillBackground(False)
    self.resize(self.WINDOW_W, self.WINDOW_H)

    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    self.setFormat(fmt)

    self._timer = QTimer(self)
    self._timer.timeout.connect(self.update)
    self._timer.start(int(1000 / self.FPS))

  def initializeGL(self) -> None:
    try:
      live2d.glInit()
      self.model = live2d.Model()
      self.model.LoadModelJson(self._model_json)
      self.model.Resize(self.width(), self.height())
      # 待机动作：空闲时随机 Idle 组动作
      self.model.StartRandomMotion('Idle', priority=1)
    except Exception:
      self.init_failed = True

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

  # 点按命中模型播 TapBody 动作，未命中播任意动作（坐标需乘 devicePixelRatio，高 DPI 已知坑）
  def _on_pet_tap(self, pos) -> None:
    if not self.model:
      return
    scale = self.devicePixelRatioF()
    x, y = pos.x() * scale, pos.y() * scale
    if self.model.IsAreaHit('Body', x, y):
      self.model.StartRandomMotion('TapBody')
    else:
      self.model.StartRandomMotion()

  # 非拖拽移动：视线跟随
  def _on_pointer_move(self, pos) -> None:
    if not self.model:
      return
    scale = self.devicePixelRatioF()
    self.model.Drag(pos.x() * scale, pos.y() * scale)
