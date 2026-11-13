# -*- coding: utf-8 -*-
import os
from typing import Callable, Optional

import live2d
from OpenGL.GL import GL_FRAMEBUFFER, GL_RGBA, GL_UNSIGNED_BYTE, glBindFramebuffer, glReadPixels
from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QRegion, QSurfaceFormat
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
  # 透明度占用图：固定逻辑网格（与分辨率/DPI 解耦），每格 max-alpha 超阈值记实体
  OCC_COLS: int = 40
  OCC_ROWS: int = 60
  # 占用图更新间隔（帧），30fps 下 6 帧 ≈ 200ms
  OCC_INTERVAL: int = 6
  # alpha 实体阈值（0-255）
  ALPHA_THRESHOLD: int = 32

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
    # 透明度占用图（None=未生成/读回失败 → 矩形命中兜底）
    self.occupancy: Optional[bytes] = None
    # 当前已应用到 setMask 的命中网格（未变化时跳过 setMask，防 region 抖动）
    self._mask_grid: bytes = b''
    self._frame_count: int = 0
    # LIVE2D_DEBUG_HIT=1 时叠加绘制占用图红框，调阈值/网格密度用
    # self._debug_hit: bool = os.environ.get('LIVE2D_DEBUG_HIT') == '1'
    self._debug_hit: bool = False

    self._init_pet_shell(on_restore, on_quit)
    # 关键坑位：QOpenGLWidget 在透明顶层窗中需关闭自动填充背景（live2d-py issue #30）
    self.setAutoFillBackground(False)
    self.resize(self.WINDOW_W, self.WINDOW_H)

    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    self.setFormat(fmt)

    self._timer = QTimer(self)
    self._timer.timeout.connect(self._tick)
    self._timer.start(int(1000 / self.FPS))

  # 每帧：轮询全局光标做视线跟随（与命中测试解耦，光标在窗外移动也能注视），再触发重绘
  def _tick(self) -> None:
    if self.model:
      scale = self.devicePixelRatioF()
      pos = self.mapFromGlobal(QCursor.pos())
      self.model.Drag(pos.x() * scale, pos.y() * scale)
    self.update()

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
    self._frame_count += 1
    if self._frame_count % self.OCC_INTERVAL == 0:
      self._update_occupancy()
    if self._debug_hit:
      self._draw_occupancy_debug()
    # 待机动作播完后自动补下一段，保持模型"活着"
    if self.model.IsMotionFinished():
      self.model.StartRandomMotion('Idle', priority=1)

  # 读回 framebuffer alpha 生成占用图：每格稀疏采样 2x2，任一像素超阈值记实体
  # 命中区域由 setMask(QRegion) 实现：HTTRANSPARENT 只对同线程窗口有效，跨进程点穿必须改窗口 region
  def _update_occupancy(self) -> None:
    # 拖拽中冻结 mask：region 变化可能打断拖拽链
    if self._drag_offset is not None:
      return
    try:
      dpr = self.devicePixelRatioF()
      fb_w = max(1, int(self.width() * dpr))
      fb_h = max(1, int(self.height() * dpr))
      # 读回前显式绑定本控件 framebuffer：live2d Draw 可能切换绑定，直接读会拿到错误/全空数据
      glBindFramebuffer(GL_FRAMEBUFFER, self.defaultFramebufferObject())
      raw = glReadPixels(0, 0, fb_w, fb_h, GL_RGBA, GL_UNSIGNED_BYTE)
      if not raw or len(raw) < fb_w * fb_h * 4:
        return
      occ = bytearray(self.OCC_COLS * self.OCC_ROWS)
      for row in range(self.OCC_ROWS):
        # glReadPixels 原点在左下：逻辑行（自上而下）映射 buffer 行需翻转；采样点钳制到 [0, fb-1]
        y0 = max(0, fb_h - 1 - int((row + 1) * fb_h / self.OCC_ROWS))
        y1 = max(0, fb_h - 1 - int(row * fb_h / self.OCC_ROWS))
        for col in range(self.OCC_COLS):
          x0 = min(fb_w - 1, int(col * fb_w / self.OCC_COLS))
          x1 = min(fb_w - 1, int((col + 1) * fb_w / self.OCC_COLS))
          for sy in (y0, y1):
            base0 = (sy * fb_w + x0) * 4 + 3
            base1 = (sy * fb_w + x1) * 4 + 3
            if raw[base0] > self.ALPHA_THRESHOLD or raw[base1] > self.ALPHA_THRESHOLD:
              occ[row * self.OCC_COLS + col] = 1
              break
      if not any(occ):
        # 退化：全零视为读回失败，恢复矩形命中（宁可不可点穿，也不能整窗变死窗）
        self.occupancy = None
        self.clearMask()
        return
      # 调试显示用 1 格膨胀图；命中 mask 用 2 格膨胀（mask 同时裁绘制，留余量防动画边缘被裁）
      self.occupancy = bytes(self._dilate(occ, 1))
      mask_grid = self._dilate(occ, 2)
      if bytes(mask_grid) != self._mask_grid:
        self._mask_grid = bytes(mask_grid)
        self._apply_hit_mask(mask_grid)
    except Exception:
      # 读回失败保持 None：命中测试退化为矩形，行为不回归
      self.occupancy = None
      self.clearMask()

  # 占用图 8 邻域膨胀 radius 格
  def _dilate(self, src: bytearray, radius: int) -> bytearray:
    out = bytearray(len(src))
    for r in range(self.OCC_ROWS):
      for c in range(self.OCC_COLS):
        if not src[r * self.OCC_COLS + c]:
          continue
        for dr in range(-radius, radius + 1):
          for dc in range(-radius, radius + 1):
            rr, cc = r + dr, c + dc
            if 0 <= rr < self.OCC_ROWS and 0 <= cc < self.OCC_COLS:
              out[rr * self.OCC_COLS + cc] = 1
    return out

  # 实体格按行合并成矩形集，设为窗口 region：命中区外的点由 OS 直接投给下层窗口（真点穿）
  def _apply_hit_mask(self, mask_grid: bytearray) -> None:
    cw = self.width() / self.OCC_COLS
    ch = self.height() / self.OCC_ROWS
    region = QRegion()
    for r in range(self.OCC_ROWS):
      c = 0
      while c < self.OCC_COLS:
        if not mask_grid[r * self.OCC_COLS + c]:
          c += 1
          continue
        c0 = c
        while c < self.OCC_COLS and mask_grid[r * self.OCC_COLS + c]:
          c += 1
        x0, x1 = int(c0 * cw), int(c * cw)
        y0, y1 = int(r * ch), int((r + 1) * ch)
        region |= QRegion(QRect(x0, y0, x1 - x0, y1 - y0))
    self.setMask(region)

  # 调试：占用图实体格叠加红色描边
  def _draw_occupancy_debug(self) -> None:
    occ = self.occupancy
    if not occ:
      return
    cw = self.width() / self.OCC_COLS
    ch = self.height() / self.OCC_ROWS
    painter = QPainter(self)
    painter.setPen(QPen(QColor(255, 0, 0, 140)))
    painter.setBrush(Qt.NoBrush)
    for r in range(self.OCC_ROWS):
      for c in range(self.OCC_COLS):
        if occ[r * self.OCC_COLS + c]:
          painter.drawRect(QRectF(c * cw, r * ch, cw, ch))
    painter.end()

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
