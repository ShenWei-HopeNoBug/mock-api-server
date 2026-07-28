# -*- coding: utf-8 -*-
import os
import sys

# 构建配置由 build.py 在打包时生成 _build_config.py 模块，
# 编译进每个 exe 的 PYZ 中，实现同目录下多个 exe 各自独立配置。
# 开发模式下 _build_config.py 不存在，走默认值。
try:
  from _build_config import MITMPROXY_LOG, VERSION
except ImportError:
  MITMPROXY_LOG = True
  VERSION = 'v0.0.0'


def _resource_path(relative: str) -> str:
  """返回资源文件绝对路径，兼容开发模式与 PyInstaller 打包模式"""
  if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
  else:
    base = os.path.dirname(os.path.abspath(__file__))
  return os.path.join(base, relative)


# 应用图标路径
APP_ICON = _resource_path('assets/app.ico')