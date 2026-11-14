# -*- coding: utf-8 -*-
import json
import os
import sys

from config.work_file import SYSTEM_DIR
from lib.logger_lib import APP_LOGGER

# 构建配置由 build.py 在打包时生成 _build_config.py 模块，
# 编译进每个 exe 的 PYZ 中，实现同目录下多个 exe 各自独立配置。
# 开发模式下 _build_config.py 不存在，走默认值。
try:
  from _build_config import MCP_LOG, MITMPROXY_LOG, VERSION
except ImportError:
  MITMPROXY_LOG = True
  MCP_LOG = True
  # 开发模式下版本号与窗口标题口径一致，取自 pyproject.toml
  from config.globals import version
  VERSION = version


def _resource_path(relative: str) -> str:
  """返回资源文件绝对路径，兼容开发模式与 PyInstaller 打包模式"""
  if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
  else:
    base = os.path.dirname(os.path.abspath(__file__))
  return os.path.join(base, relative)


# 应用图标路径
APP_ICON = _resource_path('assets/app.ico')

# Live2D 桌宠模型路径（官方示例模型，发布前需确认分发授权）
LIVE2D_MODEL_JSON = _resource_path('assets/live2d/hiyori/Hiyori.model3.json')

# 桌宠模型外置配置：应用工作目录 system/ 下（与 history.json 同基，打包后=exe 同目录）
# 换模型 = 编辑该文件 + 放置模型文件，代码零改；缺失/损坏时回退内嵌默认
PET_MODEL_CONFIG_PATH = os.path.join(SYSTEM_DIR, 'pet_model.json')

_PET_MODEL_DEFAULT = {
  'model_json': 'assets/live2d/hiyori/Hiyori.model3.json',
  'window_w': 200,
  'window_h': 300,
  'idle_group': 'Idle',
  'tap_group': 'TapBody',
  'hit_area': 'Body',
}


# 配置内模型路径解析：assets/ 前缀→内嵌资源；绝对路径→原样；其他相对路径→工作目录基（打包后=exe 同目录）
def _resolve_pet_model_path(raw: str) -> str:
  if os.path.isabs(raw):
    return raw
  if raw.startswith('assets/') or raw.startswith('assets\\'):
    return _resource_path(raw)
  return os.path.abspath(raw)


# 加载桌宠模型配置：文件缺失/JSON 损坏 → 全默认；字段非法类型 → 该项回默认（部分坏不拖垮整体）
# model_json 配置指向不存在文件 → 回退内嵌模型路径（仍不存在则由调用方走降级球）
def load_pet_model_config() -> dict:
  cfg = dict(_PET_MODEL_DEFAULT)
  cfg['model_json'] = LIVE2D_MODEL_JSON
  try:
    with open(PET_MODEL_CONFIG_PATH, 'r', encoding='utf-8') as f:
      data = json.load(f)
  except FileNotFoundError:
    data = {}  # 文件缺失是正常态（首跑/未配置），静默默认
  except Exception as e:
    APP_LOGGER.warning(f'桌宠模型配置解析失败，回退内嵌默认：{PET_MODEL_CONFIG_PATH}（{e}）')
    data = None
  if isinstance(data, dict):
    for key in ('window_w', 'window_h'):
      val = data.get(key)
      if isinstance(val, int) and not isinstance(val, bool) and val > 0:
        cfg[key] = val
    for key in ('idle_group', 'tap_group', 'hit_area'):
      val = data.get(key)
      if isinstance(val, str):
        cfg[key] = val
    raw = data.get('model_json')
    if isinstance(raw, str) and raw:
      resolved = _resolve_pet_model_path(raw)
      if os.path.exists(resolved):
        cfg['model_json'] = resolved
      else:
        APP_LOGGER.warning(f'桌宠模型文件不存在，回退内嵌模型：{resolved}')
  return cfg


# 首次进入桌宠时写默认模板（可发现性：打包用户能看到字段并自行修改）；已存在不覆盖
def ensure_pet_model_config() -> None:
  if os.path.exists(PET_MODEL_CONFIG_PATH):
    return
  try:
    os.makedirs(SYSTEM_DIR, exist_ok=True)
    with open(PET_MODEL_CONFIG_PATH, 'w', encoding='utf-8') as f:
      json.dump(_PET_MODEL_DEFAULT, f, ensure_ascii=False, indent=2)
      f.write('\n')
  except Exception:
    pass