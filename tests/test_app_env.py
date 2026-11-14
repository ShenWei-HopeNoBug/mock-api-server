# -*- coding: utf-8 -*-
import json
import os

import app_env


def _write_cfg(tmp_path, data) -> None:
  (tmp_path / 'system').mkdir(exist_ok=True)
  (tmp_path / 'system' / 'pet_model.json').write_text(
    json.dumps(data) if not isinstance(data, str) else data, encoding='utf-8',
  )


def test_missing_config_returns_defaults(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  cfg = app_env.load_pet_model_config()
  assert cfg['model_json'] == app_env.LIVE2D_MODEL_JSON
  assert (cfg['window_w'], cfg['window_h']) == (200, 300)
  assert cfg['idle_group'] == 'Idle' and cfg['tap_group'] == 'TapBody' and cfg['hit_area'] == 'Body'


def test_broken_json_returns_defaults(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  _write_cfg(tmp_path, '{not json')
  assert app_env.load_pet_model_config()['model_json'] == app_env.LIVE2D_MODEL_JSON


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
  # assets/ 前缀 → _resource_path 基（文件须存在才会被采用）
  _write_cfg(tmp_path, {'model_json': 'assets/live2d/hiyori/Hiyori.model3.json'})
  assert app_env.load_pet_model_config()['model_json'] == app_env.LIVE2D_MODEL_JSON
  # 绝对路径 → 原样返回
  model = tmp_path / 'm' / 'm.model3.json'
  model.parent.mkdir()
  model.write_text('{}', encoding='utf-8')
  _write_cfg(tmp_path, {'model_json': str(model)})
  assert app_env.load_pet_model_config()['model_json'] == str(model)
  # 相对路径 → 工作目录基
  rel = tmp_path / 'models' / 'r.model3.json'
  rel.parent.mkdir()
  rel.write_text('{}', encoding='utf-8')
  _write_cfg(tmp_path, {'model_json': 'models/r.model3.json'})
  assert app_env.load_pet_model_config()['model_json'] == os.path.abspath('models/r.model3.json')


def test_missing_configured_model_falls_back_to_bundled(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  _write_cfg(tmp_path, {'model_json': 'models/nothing.model3.json'})
  assert app_env.load_pet_model_config()['model_json'] == app_env.LIVE2D_MODEL_JSON


def test_ensure_writes_template_once(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  app_env.ensure_pet_model_config()
  assert os.path.exists(app_env.PET_MODEL_CONFIG_PATH)
  written = json.loads((tmp_path / 'system' / 'pet_model.json').read_text(encoding='utf-8'))
  assert written == app_env._PET_MODEL_DEFAULT
  # 已存在不覆盖
  (tmp_path / 'system' / 'pet_model.json').write_text('{}', encoding='utf-8')
  app_env.ensure_pet_model_config()
  assert (tmp_path / 'system' / 'pet_model.json').read_text(encoding='utf-8') == '{}'
