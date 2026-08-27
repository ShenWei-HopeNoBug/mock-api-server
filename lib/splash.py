# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
  QWidget, QLabel, QVBoxLayout, QProgressBar, QFrame,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer

import time
from typing import Callable, Optional
from lib.decorate import create_thread

"""启动阶段文案，key 为进度百分比阈值，value 为该阶段的启动文案
当进度 >= 某个 key 时显示对应文案，直到达到下一个 key
"""
STARTUP_MESSAGES = {
  0: '正在初始化应用环境…',
  30: '正在启动 APP_SERVER 服务…',
  70: '正在加载主窗口…',
  90: '即将就绪…',
  100: '启动完成',
}

# 百分比后缀模板，拼在文案后面，如：正在启动 APP_SERVER 服务… (30%)
PERCENT_TEMPLATE = ' ({percent}%)'

# 启动动画窗口尺寸
SPLASH_WIDTH = 360
SPLASH_HEIGHT = 160

# 所有阶段进度值排序，用于在 set_phase 中计算下一个阶段目标值
_PHASE_KEYS = sorted(STARTUP_MESSAGES.keys())


class StartSplash(QObject):
  """启动动画
  通过 set_phase() 在真实启动节点推进进度，子线程在两个阶段之间逐帧递增百分比
  到达下一阶段目标值 - 1 时暂停，等待 set_phase() 被调用后继续递增
  """
  # 进度变更信号，子线程 emit → 主线程槽函数更新 UI（线程安全）
  percent_signal: pyqtSignal = pyqtSignal(int)

  def __init__(self) -> None:
    super().__init__()
    # 启动动画窗口
    self.splash: Optional[QWidget] = None
    # 当前进度百分比
    self.percent: int = 0
    # 动画是否已结束
    self.finished: bool = False
    # 当前阶段进度上限（下一个 set_phase 目标值 - 1），子线程递增到此暂停等待
    self._cap: int = _PHASE_KEYS[1] - 1 if len(_PHASE_KEYS) > 1 else 99

    # 启动文案标签
    self._tip_label: Optional[QLabel] = None
    # indeterminate 循环滚动进度条
    self._progress_bar: Optional[QProgressBar] = None

    self._build_ui()
    self.percent_signal.connect(self._on_percent)

  # 构建启动动画窗口 UI（无边框透明窗口 + 圆角卡片 + 文案 + 进度条）
  def _build_ui(self) -> None:
    win = QWidget()
    win.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    win.setAttribute(Qt.WA_TranslucentBackground)
    win.setFixedSize(SPLASH_WIDTH, SPLASH_HEIGHT)

    # 外层布局，用于居中卡片
    outer = QVBoxLayout(win)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setAlignment(Qt.AlignCenter)

    # 卡片容器，样式与退出蒙层一致
    card = QFrame(win)
    card.setStyleSheet('''
      QFrame {
        background-color: rgb(255, 248, 225);
        border-radius: 10px;
      }
    ''')
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(30, 30, 30, 30)
    card_layout.setSpacing(16)

    # 启动文案
    tip_label = QLabel('正在启动应用…', card)
    tip_label.setAlignment(Qt.AlignCenter)
    tip_label.setStyleSheet('font-size: 15px; color: rgb(80, 80, 80); border: none;')
    self._tip_label = tip_label

    # 进度条（indeterminate，循环滚动动画）
    progress_bar = QProgressBar(card)
    progress_bar.setRange(0, 0)
    progress_bar.setFixedWidth(280)
    progress_bar.setTextVisible(False)
    progress_bar.setStyleSheet('''
      QProgressBar {
        border: none;
        border-radius: 4px;
        background-color: rgb(230, 230, 230);
        height: 8px;
      }
      QProgressBar::chunk {
        border-radius: 4px;
        background-color: rgb(97, 97, 97);
      }
    ''')
    self._progress_bar = progress_bar

    card_layout.addWidget(tip_label)
    card_layout.addWidget(progress_bar, alignment=Qt.AlignCenter)
    outer.addWidget(card)

    self.splash = win

  # 显示启动动画，初始化为 0% 阶段并启动子线程递增定时器
  def show(self) -> None:
    if self.splash is None:
      return
    self.set_phase(0)
    self.splash.show()
    self.start_percent_timer()

  def set_phase(self, percent: int) -> None:
    """设置当前启动阶段进度，由 main.py 在真实启动节点调用
      调用后更新文案与百分比，并重新计算 _cap（下一阶段目标值 - 1）供子线程继续递增
      """
    if self.finished or self.splash is None:
      return
    self.percent = percent
    # 计算下一个阶段目标值，设置进度上限为目标值 - 1
    next_phase = 100
    for k in _PHASE_KEYS:
      if k > percent:
        next_phase = k
        break
    self._cap = next_phase - 1 if next_phase > percent else 100
    self.percent_signal.emit(percent)

  # 进度变更槽函数（主线程），根据进度值更新文案与百分比后缀
  def _on_percent(self, value: int) -> None:
    if self.finished or self.splash is None:
      return
    if self._tip_label is not None:
      msg = STARTUP_MESSAGES.get(value, None)
      if msg is None:
        keys = [k for k in STARTUP_MESSAGES if k <= value]
        msg = STARTUP_MESSAGES[max(keys)] if keys else '正在启动应用…'
      self._tip_label.setText(msg + PERCENT_TEMPLATE.format(percent=value))

  def finish(self, win: QWidget, callback: Optional[Callable] = None) -> None:
    """结束启动动画，将进度设为 100% 后延迟 800ms 再关闭窗口
      延迟期间主线程可处理事件循环，让窗口完成首次绘制，避免白屏闪烁
      callback 在动画真正关闭后执行（通常传入 main_window.init）
      """
    self.set_phase(100)
    QTimer.singleShot(800, lambda: self._do_finish(win, callback))

  # 实际关闭动画窗口并触发回调（由 QTimer.singleShot 延迟调用）
  def _do_finish(self, win: QWidget, callback: Optional[Callable] = None) -> None:
    if self.splash is not None:
      self.splash.close()
      self.splash.deleteLater()
      self.splash = None
    self.finished = True
    if callback:
      callback()

  @create_thread
  def start_percent_timer(self) -> None:
    """子线程百分比递增定时器，每 0.1s 递增 1%
      到达 _cap（下一阶段目标值 - 1）时暂停，等待 set_phase() 推进后继续
      通过 percent_signal 通知主线程更新 UI，避免跨线程操作 widget
      """
    while self.percent < 99 and not self.finished:
      time.sleep(0.1)
      if self.finished:
        break
      if self.percent < self._cap:
        self.percent += 1
        self.percent_signal.emit(self.percent)
