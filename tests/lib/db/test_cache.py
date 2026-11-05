# -*- coding: utf-8 -*-
from lib.db import MockDBCache
from lib.db.constants import CURRENT_SCHEMA_VERSION


def test_same_workdir_same_instance(tmp_path):
  (tmp_path / 'data').mkdir()
  a = MockDBCache.get(str(tmp_path))
  b = MockDBCache.get(str(tmp_path))
  assert a is b
  MockDBCache.close_all()


def test_diff_workdir_diff_instance(tmp_path):
  d1, d2 = tmp_path / 'w1', tmp_path / 'w2'
  (d1 / 'data').mkdir(parents=True)
  (d2 / 'data').mkdir(parents=True)
  try:
    assert MockDBCache.get(str(d1)) is not MockDBCache.get(str(d2))
  finally:
    MockDBCache.close_all()


def test_close_removes_from_cache(tmp_path):
  (tmp_path / 'data').mkdir()
  db = MockDBCache.get(str(tmp_path))
  MockDBCache.close(str(tmp_path))
  db2 = MockDBCache.get(str(tmp_path))
  assert db2 is not db
  MockDBCache.close_all()


def test_close_all_clears_cache(tmp_path):
  (tmp_path / 'data').mkdir()
  MockDBCache.get(str(tmp_path))
  MockDBCache.close_all()
  assert MockDBCache._cache == {}


def test_migrate_idempotent_reopen(tmp_path):
  """版本号降级后重开同一库：迁移幂等执行，user_version 归位不报错"""
  (tmp_path / 'data').mkdir()
  db = MockDBCache.get(str(tmp_path))
  db._conn.execute(f'PRAGMA user_version = {CURRENT_SCHEMA_VERSION - 2}')
  MockDBCache.close_all()
  db2 = MockDBCache.get(str(tmp_path))   # 触发 v3→v5 迁移，列守卫保证幂等
  version = db2._conn.execute('PRAGMA user_version').fetchone()[0]
  assert version == CURRENT_SCHEMA_VERSION
  MockDBCache.close_all()
