# -*- coding: utf-8 -*-
import json
import os
import sys


def _load_build_config():
  """读取打包时通过 --add-data 注入的构建配置，开发模式返回空字典走默认值"""
  if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
  else:
    base = os.path.dirname(os.path.abspath(__file__))
  path = os.path.join(base, 'build_config.json')
  if os.path.exists(path):
    with open(path, encoding='utf-8') as f:
      return json.load(f)
  return {}


_cfg = _load_build_config()

MITMPROXY_LOG = _cfg.get('MITMPROXY_LOG', False)
VERSION = _cfg.get('VERSION', 'v0.0.0')