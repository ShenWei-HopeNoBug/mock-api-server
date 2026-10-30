# -*- coding: utf-8 -*-
import tomllib
from pathlib import Path


def _load_version() -> str:
  # 从 pyproject.toml 读取版本号，打包态下文件不存在时走兜底（exe 版本由 _build_config 承载）
  pyproject = Path(__file__).parent.parent / 'pyproject.toml'
  try:
    data = tomllib.loads(pyproject.read_text(encoding='utf-8'))
    return 'v' + data['project']['version']
  except Exception:
    return 'v0.0.0'


# 版本号
version = _load_version()
