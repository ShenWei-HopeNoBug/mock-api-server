# -*- coding: utf-8 -*-
import sqlite3
import threading
from typing import Callable, ContextManager, List

from lib.utils_lib import generate_uuid
from lib.logger_lib import APP_LOGGER
from config.enum.BIZ_CODE import (
  BIZ_SUCCESS,
  BIZ_DATA_EMPTY,
  BIZ_DB_ERROR,
  BIZ_UNKNOWN_ERROR,
)
from app_types.db_types import StaticData, BatchOperationResult
from .utils import _ensure_open


class StaticDataMixin:
  """
  static_data 表的数据访问 Mixin

  提供 static_data 表的 CRUD 操作，依赖宿主类提供 _conn / _lock / _transaction 等基础设施。
  需与 BaseSQLiteDB 组合使用。
  """

  # 基础设施属性声明（由宿主类 BaseSQLiteDB 提供，此处仅用于 IDE 类型提示）
  _conn: sqlite3.Connection
  _lock: threading.Lock
  _closed: bool
  _transaction: Callable[[], ContextManager[sqlite3.Connection]]
  _wal_checkpoint_passive: Callable[[], None]

  def _migrate_static(self, from_version: int, to_version: int) -> None:
    """static_data 表的 schema 版本迁移，逐版本升级"""
    if from_version < 3 <= to_version:
      # v2 → v3: 删除未使用的 idx_static_url 索引
      self._conn.execute('DROP INDEX IF EXISTS idx_static_url')
      APP_LOGGER.info('StaticDataMixin schema 迁移: v2 → v3, 删除未使用的 idx_static_url 索引')

  # 批量写静态资源到 DB
  @_ensure_open(default={"success": False, "status_code": BIZ_UNKNOWN_ERROR, "status_msg": "批量插入失败", "affected_count": 0})
  def batch_insert_static(self, urls: List[str]) -> BatchOperationResult:
    """
    批量写入静态资源 URL，写入后触发 PASSIVE checkpoint

    纯 INSERT 不去重，id 统一用 generate_uuid 生成。
    返回成功状态和实际插入的记录数。
    """
    if not urls:
      return {"success": False, "status_code": BIZ_DATA_EMPTY, "status_msg": "数据为空", "affected_count": 0}

    insert_sql = 'INSERT INTO static_data (id, url, type) VALUES (?, ?, ?)'
    insert_data = []
    for url in urls:
      if not url or not url.strip():
        continue
      static_id = generate_uuid()
      insert_data.append((static_id, url, 'MITMPROXY'))

    try:
      with self._transaction() as conn:
        conn.executemany(insert_sql, insert_data)
      APP_LOGGER.info(f'MockDB batch_insert_static 写入 {len(insert_data)}/{len(urls)} 条')
      return {"success": True, "status_code": BIZ_SUCCESS, "status_msg": "成功", "affected_count": len(insert_data)}
    except Exception as e:
      return {"success": False, "status_code": BIZ_DB_ERROR, "status_msg": f"批量插入失败: {str(e)}", "affected_count": 0}
    finally:
      try:
        self._wal_checkpoint_passive()
      except Exception as e:
        APP_LOGGER.error(f'MockDB batch_insert_static checkpoint 失败: {e}')

  # 查静态资源列表
  @_ensure_open(default=[])
  def get_static_list(self, reverse: bool = False) -> List[StaticData]:
    """查询全部静态资源列表，可按时间正序/倒序排列"""
    order = 'DESC, url DESC' if reverse else 'ASC, url ASC'
    sql = f'SELECT id, url, type, created_at, updated_at FROM static_data ORDER BY created_at {order}'
    with self._lock:
      cursor = self._conn.execute(sql)
      rows = cursor.fetchall()
    result = []
    for row in rows:
      result.append({
        'id': row[0],
        'url': row[1],
        'type': row[2],
        'created_at': row[3],
        'updated_at': row[4],
      })
    return result
