# -*- coding: utf-8 -*-

# 构建配置由 build.py 在打包时生成 _build_config.py 模块，
# 编译进每个 exe 的 PYZ 中，实现同目录下多个 exe 各自独立配置。
# 开发模式下 _build_config.py 不存在，走默认值。
try:
  from _build_config import MITMPROXY_LOG, VERSION
except ImportError:
  MITMPROXY_LOG = True
  VERSION = 'v0.0.0'