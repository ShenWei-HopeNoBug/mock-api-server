# -*- coding: utf-8 -*-
import ctypes
import multiprocessing
import os
import sys
import traceback as tb_module
from types import TracebackType
from typing import Optional, Type

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import app_env
from app_types.app_gui_types import AppServerRunningData
from lib.app_lib import (
  bring_to_front,
  find_running_app_pid,
  get_memory_name,
  is_app_running,
  is_app_work_dir_valid,
  run_blocking_with_events,
)
from lib.logger_lib import APP_LOGGER, configure_logging
from lib.splash import StartSplash
from module.app_server import start_app_server
from qt_win.app import MainWindow


def exception_handler(
    exception_type: Type[BaseException],
    value: BaseException,
    traceback: Optional[TracebackType],
) -> None:
  """全局异常处理器"""
  tb_str = ''.join(tb_module.format_exception(exception_type, value, traceback))
  APP_LOGGER.error(f'APP全局程序异常捕获：{value}\n{tb_str}')
  # 显示异常信息的对话框
  QMessageBox.critical(None, "程序异常", f"发生异常：{value}")
  sys.exit(1)


if __name__ == '__main__':
  # 防止窗口开进程新打开个 GUI 窗口
  multiprocessing.freeze_support()
  # 主进程独占文件/控制台日志 handler，起 QueueListener 汇聚子进程日志（须在任何子进程 spawn 之前）
  configure_logging('parent')
  # 设置 Windows 任务栏 AppUserModelID，使任务栏图标使用自定义图标而非 Python 默认图标
  ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('mock-api-server')
  # Qt6 WebEngine 在 Windows 上跨进程 GPU 纹理共享存在周期性闪帧问题（上游未修复，QTBUG-142355 同类），
  # --in-process-gpu 将 GPU 工作并入浏览器进程内规避，需在 QtWebEngine 初始化前设置；setdefault 保留外部覆盖能力
  os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--in-process-gpu')
  # Qt6 WebEngine Widgets 要求共享 OpenGL 上下文
  QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
  # 禁止屏幕设置了缩放导致显示不一致
  QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
  app: QApplication = QApplication(sys.argv)
  # 固定 windowsvista 样式：避免 Qt6 默认 windows11 样式跟随系统深色模式导致字体/控件观感异常
  app.setStyle('windowsvista')
  # 设置应用图标（任务栏/标题栏）
  app.setWindowIcon(QIcon(app_env.APP_ICON))
  # 全局异常捕获
  sys.excepthook = exception_handler

  # 检查 APP 是否已经在运行
  if is_app_running(app_name=get_memory_name()):
    # 查找已运行的实例
    pid: Optional[int] = find_running_app_pid()
    if pid:
      # 将已运行的实例窗口置顶
      brought = bring_to_front(pid)
      if brought:
        QMessageBox.information(None, '提示', '程序已经在运行中，已将窗口置顶！')
      else:
        QMessageBox.information(None, '提示', '程序已经在运行中，但未检测到可见窗口（可能仍在启动中），请稍后查看！')
    else:
      QMessageBox.information(None, '提示', '程序已经在运行中！')
    sys.exit(1)

  # 检查 APP 运行路径是否合法
  if not is_app_work_dir_valid():
    QMessageBox.critical(None, '程序异常', '程序运行路径异常（路径包含中文或路径不存在）！')
    sys.exit(1)

  start_splash: StartSplash = StartSplash()
  # 启动动画对象
  start_splash.show()
  # 确保启动动画立即渲染
  app.processEvents()

  # 阶段 30%：启动 APP_SERVER 服务（子线程执行，主线程保持事件循环以更新启动动画）
  start_splash.set_phase(30)
  app_sever_running_data: AppServerRunningData = run_blocking_with_events(app, start_app_server)

  # 阶段 70%：加载主窗口
  start_splash.set_phase(70)
  main_window: MainWindow = MainWindow(app_sever_running_data=app_sever_running_data)
  app.processEvents()

  # 阶段 90%：展示窗口
  start_splash.set_phase(90)
  main_window.show()
  app.processEvents()

  # 结束启动动画（100%），动画结束后执行 init
  start_splash.finish(main_window, callback=main_window.init)

  sys.exit(app.exec())
