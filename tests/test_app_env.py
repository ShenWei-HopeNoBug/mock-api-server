# -*- coding: utf-8 -*-
import json
import os

import app_env


def _write_cfg(tmp_path, data) -> None:
  (tmp_path / 'system').mkdir(exist_ok=True)
  (tmp_path / 'system' / 'pet_model.json').write_text(
    json.dumps(data) if not isinstance(data, str) else data, encoding='utf-8',
  )


# ---------- load_pet_model_config（beta 收敛：无内嵌兜底，空串=未配置） ----------


def test_missing_config_returns_empty_model(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  cfg = app_env.load_pet_model_config()
  assert cfg['model_json'] == ''
  assert (cfg['window_w'], cfg['window_h']) == (200, 300)
  assert cfg['idle_group'] == 'Idle' and cfg['tap_group'] == 'TapBody' and cfg['hit_area'] == 'Body'


def test_broken_json_returns_empty_model(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  _write_cfg(tmp_path, '{not json')
  assert app_env.load_pet_model_config()['model_json'] == ''


def test_invalid_field_types_fall_back_per_field(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  _write_cfg(tmp_path, {
    'window_w': 'abc', 'window_h': -1, 'idle_group': 123,
    'tap_group': '', 'hit_area': 'Head',
  })
  cfg = app_env.load_pet_model_config()
  assert cfg['window_w'] == 200 and cfg['window_h'] == 300 and cfg['idle_group'] == 'Idle'
  assert cfg['tap_group'] == '' and cfg['hit_area'] == 'Head'


def test_model_path_resolution(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  # 相对路径 → app 根（CWD）为基，与 ./pets 同级
  model = tmp_path / 'pets' / 'hiyori' / 'h.model3.json'
  model.parent.mkdir(parents=True)
  model.write_text('{}', encoding='utf-8')
  _write_cfg(tmp_path, {'model_json': 'pets/hiyori/h.model3.json'})
  assert app_env.load_pet_model_config()['model_json'] == os.path.abspath('pets/hiyori/h.model3.json')
  # 绝对路径 → 原样返回
  _write_cfg(tmp_path, {'model_json': str(model)})
  assert app_env.load_pet_model_config()['model_json'] == str(model)


def test_missing_configured_model_returns_empty(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  _write_cfg(tmp_path, {'model_json': 'pets/nothing.model3.json'})
  assert app_env.load_pet_model_config()['model_json'] == ''


def test_empty_model_json_stays_empty(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  _write_cfg(tmp_path, {'model_json': ''})
  assert app_env.load_pet_model_config()['model_json'] == ''


# ---------- ensure_pet_model_config ----------


def test_ensure_writes_template_once(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  app_env.ensure_pet_model_config()
  assert os.path.exists(app_env.PET_MODEL_CONFIG_PATH)
  # pets 全局目录连带创建（与 system 同级）
  assert os.path.isdir(tmp_path / 'pets')
  written = json.loads((tmp_path / 'system' / 'pet_model.json').read_text(encoding='utf-8'))
  assert written == app_env._PET_MODEL_DEFAULT
  # 已存在不覆盖，但目录仍补建
  (tmp_path / 'system' / 'pet_model.json').write_text('{}', encoding='utf-8')
  os.rmdir(tmp_path / 'pets')
  app_env.ensure_pet_model_config()
  assert (tmp_path / 'system' / 'pet_model.json').read_text(encoding='utf-8') == '{}'
  assert os.path.isdir(tmp_path / 'pets')
