# -*- coding: utf-8 -*-
import json
import os

from config.work_file import PET_MODEL_CONFIG_PATH, PETS_DIR, SYSTEM_DIR
from lib.logger_lib import APP_LOGGER

# 桌宠模型外置配置：应用工作目录 system/ 下（与 history.json 同基，打包后=exe 同目录）
# beta 收敛：无内嵌兜底——model_json 解析不出存在的文件即为未配置，由调用方走图标球
_PET_MODEL_DEFAULT = {
  'model_json': 'pets/hiyori/Hiyori.model3.json',
  'window_w': 200,
  'window_h': 300,
  'idle_group': 'Idle',
  'tap_group': 'TapBody',
  'hit_area': 'Body',
}


# 配置内模型路径解析：绝对路径→原样；相对路径→app 根为基（与 system/pets 同级 ./ 锚定一致，打包后=exe 同目录）
def _resolve_pet_model_path(raw: str) -> str:
  if os.path.isabs(raw):
    return raw
  return os.path.abspath(raw)


# 加载桌宠模型配置：文件缺失/JSON 损坏 → model_json 空串；字段非法类型 → 该项回默认（部分坏不拖垮整体）
# model_json 配置指向不存在文件 → 空串 + warning（提示应放位置）；空串即未配置，调用方走图标球
def load_pet_model_config() -> dict:
  cfg = dict(_PET_MODEL_DEFAULT)
  cfg['model_json'] = ''
  try:
    with open(PET_MODEL_CONFIG_PATH, 'r', encoding='utf-8') as f:
      data = json.load(f)
  except FileNotFoundError:
    data = {}  # 文件缺失是正常态（首跑/未配置），静默未配置
  except Exception as e:
    APP_LOGGER.warning(f'桌宠模型配置解析失败，降级图标球：{PET_MODEL_CONFIG_PATH}（{e}）')
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
        APP_LOGGER.warning(f'桌宠模型文件不存在，降级图标球：{resolved}')
  return cfg


# 首次进入桌宠时写默认模板 + 建 pets 全局目录（可发现性：用户能看到字段并自行修改、有目录可放模型）
# 目录每次都 ensure（配置已存在但目录被删也要补建）；模板已存在不覆盖
def ensure_pet_model_config() -> None:
  try:
    os.makedirs(SYSTEM_DIR, exist_ok=True)
    os.makedirs(PETS_DIR, exist_ok=True)
    if os.path.exists(PET_MODEL_CONFIG_PATH):
      return
    with open(PET_MODEL_CONFIG_PATH, 'w', encoding='utf-8') as f:
      json.dump(_PET_MODEL_DEFAULT, f, ensure_ascii=False, indent=2)
      f.write('\n')
  except Exception:
    pass
