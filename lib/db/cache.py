# -*- coding: utf-8 -*-
import os
from typing import Dict

from config.work_file import DB_DATA_PATH
from .mock_db import MockDB


class MockDBCache:
  """MockDB 实例缓存管理（静态类，以 work_dir 绝对路径为 key 懒加载）"""

  _cache: Dict[str, 'MockDB'] = {}

  @classmethod
  def get(cls, work_dir: str = '.') -> MockDB:
    cache_key = os.path.abspath(work_dir)
    if cache_key not in cls._cache:
      db_path = f'{work_dir}{DB_DATA_PATH}'
      cls._cache[cache_key] = MockDB(os.path.abspath(db_path))
    return cls._cache[cache_key]

  @classmethod
  def close(cls, work_dir: str = '.') -> None:
    cache_key = os.path.abspath(work_dir)
    mock_db = cls._cache.pop(cache_key, None)
    if mock_db:
      mock_db.close()

  @classmethod
  def close_all(cls) -> None:
    for mock_db in cls._cache.values():
      mock_db.close()
    cls._cache.clear()
