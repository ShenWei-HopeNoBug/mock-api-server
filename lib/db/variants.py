# -*- coding: utf-8 -*-
import sqlite3
import threading
from typing import Callable, ContextManager, List, Optional

from lib.utils_lib import generate_uuid, JsonFormat
from lib.logger_lib import APP_LOGGER
from config.enum import DATABASE
from config.enum.BIZ_CODE import (
  BIZ_SUCCESS,
  BIZ_PARAM_MISSING,
  BIZ_DATA_NOT_FOUND,
  BIZ_DB_ERROR,
  BIZ_UNKNOWN_ERROR,
)
from app_types.db_types import (
  ApiResponseVariantInsertRecord,
  ApiResponseVariantRecord,
  ApiResponseVariant,
  OperationResult,
  OperationResultWithOptionalId,
)
from .utils import (
  _ensure_open,
  _normalize_response_variant_ids,
  _parse_response_variant_ids,
  _normalize_enabled,
  _parse_enabled,
)


class ApiResponseVariantMixin:
  """
  api_response_variants 表的数据访问 Mixin

  提供 response 变体的 CRUD 操作，以及与 api_data.response_variant_ids 列表的同步维护。
  依赖宿主类提供 _conn / _lock / _transaction 等基础设施。
  需与 BaseSQLiteDB 组合使用。
  """

  # 基础设施属性声明（由宿主类 BaseSQLiteDB 提供，此处仅用于 IDE 类型提示）
  _conn: sqlite3.Connection
  _lock: threading.Lock
  _closed: bool
  _transaction: Callable[[], ContextManager[sqlite3.Connection]]
  _wal_checkpoint_passive: Callable[[], None]

  def _migrate_variant(self, from_version: int, to_version: int) -> None:
    """api_response_variants 表的 schema 版本迁移，逐版本升级"""
    if from_version < 3 <= to_version:
      # v2 → v3: 新增 api_response_variants 表
      # @formatter:off
      self._conn.execute(
        '''
          CREATE TABLE IF NOT EXISTS api_response_variants (
            id          TEXT PRIMARY KEY,
            api_data_id TEXT NOT NULL,
            name        TEXT NOT NULL DEFAULT '',
            response    TEXT NOT NULL DEFAULT '{}',
            enabled     INTEGER NOT NULL DEFAULT 1,
            timeout     INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
            updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
          )
        '''
      )
      # @formatter:on
      self._conn.execute('CREATE INDEX IF NOT EXISTS idx_variant_api_data_id ON api_response_variants(api_data_id)')
      APP_LOGGER.info('ApiResponseVariantMixin schema 迁移: v2 → v3, 新增 response 变体支持')
    if from_version < 4 <= to_version:
      # v3 → v4: api_response_variants 新增 operator 字段
      self._conn.execute("ALTER TABLE api_response_variants ADD COLUMN operator TEXT NOT NULL DEFAULT ''")
      APP_LOGGER.info('ApiResponseVariantMixin schema 迁移: v3 → v4, api_response_variants 新增 operator 字段')

  @_ensure_open(default={"success": False, "id": None, "status_code": BIZ_UNKNOWN_ERROR, "status_msg": "插入变体失败"})
  def insert_variant(self, record: ApiResponseVariantInsertRecord) -> OperationResultWithOptionalId:
    """新增一条 response 变体，并自动追加到所属 api_data 的变体列表，成功返回 {"success": True, "id": "uuid", "status_code": 0, "status_msg": "成功"}"""
    data = {**DATABASE.API_RESPONSE_VARIANT_INSERT_DEFAULTS, **record}
    variant_id = generate_uuid()
    api_data_id = data.get('api_data_id')
    if not api_data_id:
      APP_LOGGER.warning('ApiResponseVariantMixin insert_variant 缺少 api_data_id')
      return {"success": False, "id": None, "status_code": BIZ_PARAM_MISSING, "status_msg": "缺少必填参数: api_data_id"}

    data['response'] = JsonFormat.format_json_string(data['response'])
    data['enabled'] = _normalize_enabled(data.get('enabled'))
    data['timeout'] = int(data.get('timeout', 0))

    try:
      with self._transaction() as conn:
        # 确认所属 api_data 存在，避免产生孤儿变体
        row = conn.execute('SELECT response_variant_ids FROM api_data WHERE id=?', (api_data_id,)).fetchone()
        if row is None:
          return {"success": False, "id": None, "status_code": BIZ_DATA_NOT_FOUND, "status_msg": f"关联的 API 数据不存在: {api_data_id}"}
        conn.execute(
          'INSERT INTO api_response_variants (id, api_data_id, name, response, enabled, timeout, operator) VALUES (?, ?, ?, ?, ?, ?, ?)',
          (variant_id, api_data_id, data.get('name', ''), data['response'], data['enabled'], data['timeout'], data.get('operator', '')),
        )
        # 把新变体 ID 追加到 api_data.response_variant_ids 列表
        variant_ids = _parse_response_variant_ids(row[0])
        if variant_id not in variant_ids:
          variant_ids.append(variant_id)
          conn.execute(
            '''UPDATE api_data
               SET response_variant_ids=?,
                   updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
               WHERE id = ?
            ''',
            (_normalize_response_variant_ids(variant_ids), api_data_id),
          )
      return {"success": True, "id": variant_id, "status_code": BIZ_SUCCESS, "status_msg": "成功"}
    except Exception as e:
      return {"success": False, "id": None, "status_code": BIZ_DB_ERROR, "status_msg": f"数据库操作失败: {str(e)}"}

  @_ensure_open(default={"success": False, "status_code": BIZ_UNKNOWN_ERROR, "status_msg": "更新变体失败"})
  def update_variant(self, record: ApiResponseVariantRecord) -> OperationResult:
    """按 id 更新变体（字段级合并），不允许修改所属 api_data_id，失败返回 {"success": False, "status_code": 具体错误码, "status_msg": "具体错误信息"}"""
    variant_id = record.get('id')
    if not variant_id:
      return {"success": False, "status_code": BIZ_PARAM_MISSING, "status_msg": "缺少必填参数: id"}

    with self._lock:
      row = self._conn.execute(
        'SELECT name, response, enabled, timeout, operator FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return {"success": False, "status_code": BIZ_DATA_NOT_FOUND, "status_msg": f"记录不存在: {variant_id}"}

    old = {
      'name': row[0],
      'response': row[1],
      'enabled': _parse_enabled(row[2]),
      'timeout': row[3],
      'operator': row[4],
    }
    # api_data_id 不参与合并，防止破坏绑定关系
    merged = {**old, **{k: v for k, v in record.items() if k not in ('id', 'api_data_id') and v is not None}}
    merged['response'] = JsonFormat.format_json_string(merged['response'])
    merged['enabled'] = _normalize_enabled(merged.get('enabled'))
    merged['timeout'] = int(merged.get('timeout', 0))

    try:
      with self._transaction() as conn:
        cursor = conn.execute(
          '''UPDATE api_response_variants
             SET name=?,
                 response=?,
                 enabled=?,
                 timeout=?,
                 operator=?,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE id = ?''',
          (merged['name'], merged['response'], merged['enabled'], merged['timeout'], merged.get('operator', ''), variant_id),
        )
        return {"success": True, "status_code": BIZ_SUCCESS, "status_msg": "成功"}
    except Exception as e:
      return {"success": False, "status_code": BIZ_DB_ERROR, "status_msg": f"数据库操作失败: {str(e)}"}

  @_ensure_open(default={"success": False, "status_code": BIZ_UNKNOWN_ERROR, "status_msg": "删除变体失败"})
  def delete_variant(self, variant_id: str) -> OperationResult:
    """按 id 删除变体，并同步从 api_data.response_variant_ids 中移除，失败返回 {"success": False, "status_code": 具体错误码, "status_msg": "具体错误信息"}"""
    if not variant_id:
      return {"success": False, "status_code": BIZ_PARAM_MISSING, "status_msg": "缺少必填参数: id"}

    with self._lock:
      row = self._conn.execute(
        'SELECT api_data_id FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return {"success": False, "status_code": BIZ_DATA_NOT_FOUND, "status_msg": f"记录不存在: {variant_id}"}
    api_data_id = row[0]

    try:
      with self._transaction() as conn:
        conn.execute('DELETE FROM api_response_variants WHERE id=?', (variant_id,))
        list_row = conn.execute('SELECT response_variant_ids FROM api_data WHERE id=?', (api_data_id,)).fetchone()
        if list_row:
          variant_ids = _parse_response_variant_ids(list_row[0])
          if variant_id in variant_ids:
            variant_ids.remove(variant_id)
            conn.execute(
              '''UPDATE api_data
                 SET response_variant_ids=?,
                     updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
                 WHERE id = ?
              ''',
              (_normalize_response_variant_ids(variant_ids), api_data_id),
            )
      return {"success": True, "status_code": BIZ_SUCCESS, "status_msg": "成功"}
    except Exception as e:
      return {"success": False, "status_code": BIZ_DB_ERROR, "status_msg": f"数据库操作失败: {str(e)}"}

  @_ensure_open(default=None)
  def get_variant_by_id(self, variant_id: str) -> Optional[ApiResponseVariant]:
    """按 id 主键查询单条变体，不存在时返回 None"""
    if not variant_id:
      return None
    with self._lock:
      row = self._conn.execute(
        'SELECT id, api_data_id, name, response, enabled, timeout, operator, created_at, updated_at FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return None

    result: ApiResponseVariant = {
      'id': row[0],
      'api_data_id': row[1],
      'name': row[2],
      'response': row[3],
      'enabled': _parse_enabled(row[4]),
      'timeout': row[5],
      'operator': row[6],
      'created_at': row[7],
      'updated_at': row[8],
    }
    return result

  @_ensure_open(default=[])
  def get_variants_by_api_id(
      self,
      api_data_id: str,
      enabled: Optional[bool] = None,
  ) -> List[ApiResponseVariant]:
    """按 api_data_id 查询变体列表，结果按 api_data.response_variant_ids 顺序排列；

    enabled=None 返回全部，enabled=True 返回启用，enabled=False 返回禁用
    """
    if not api_data_id:
      return []
    sql = 'SELECT id, api_data_id, name, response, enabled, timeout, operator, created_at, updated_at FROM api_response_variants WHERE api_data_id=?'
    params: List[str] = [api_data_id]
    if enabled is True:
      sql += ' AND enabled=1'
    elif enabled is False:
      sql += ' AND enabled=0'

    with self._lock:
      rows = self._conn.execute(sql, params).fetchall()
      list_row = self._conn.execute('SELECT response_variant_ids FROM api_data WHERE id=?', (api_data_id,)).fetchone()
    order_map = {}
    if list_row:
      order_map = {v: i for i, v in enumerate(_parse_response_variant_ids(list_row[0]))}

    result = []
    for row in rows:
      result.append({
        'id': row[0],
        'api_data_id': row[1],
        'name': row[2],
        'response': row[3],
        'enabled': _parse_enabled(row[4]),
        'timeout': row[5],
        'operator': row[6],
        'created_at': row[7],
        'updated_at': row[8],
      })
    # 按 api_data.response_variant_ids 中的顺序排列，未在列表中的放最后
    result.sort(key=lambda v: order_map.get(v['id'], len(order_map)))
    return result

  @_ensure_open(default={"success": False, "id": None, "status_code": BIZ_UNKNOWN_ERROR, "status_msg": "复制变体失败"})
  def copy_variant(self, variant_id: str, api_data_id: str) -> OperationResultWithOptionalId:
    """复制一条 response 变体，并绑定到指定的 api_data 上。

    新变体的 enabled 固定为 False（默认不启用），不复制源变体的启用状态。

    variant_id: 源变体 ID
    api_data_id: 目标 api_data ID（可以与源变体所属的 api_data 不同）
    
    返回：成功返回 {"success": True, "id": "新变体ID", "status_code": 0, "status_msg": "成功"}，失败返回 {"success": False, "id": None, "status_code": 具体错误码, "status_msg": "具体错误信息"}
    """
    if not variant_id or not api_data_id:
      return {"success": False, "id": None, "status_code": BIZ_PARAM_MISSING, "status_msg": "缺少必填参数: variant_id 或 api_data_id"}

    with self._lock:
      row = self._conn.execute(
        'SELECT name, response, enabled, timeout, operator FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return {"success": False, "id": None, "status_code": BIZ_DATA_NOT_FOUND, "status_msg": f"源变体不存在: {variant_id}"}

    name, response, _, timeout, operator = row
    new_variant_id = generate_uuid()
    new_name = f'{name} (副本)' if name else '副本'

    try:
      with self._transaction() as conn:
        target_row = conn.execute(
          'SELECT response_variant_ids FROM api_data WHERE id=?', (api_data_id,)
        ).fetchone()
        if target_row is None:
          return {"success": False, "id": None, "status_code": BIZ_DATA_NOT_FOUND, "status_msg": f"目标 API 数据不存在: {api_data_id}"}

        conn.execute(
          'INSERT INTO api_response_variants (id, api_data_id, name, response, enabled, timeout, operator) VALUES (?, ?, ?, ?, ?, ?, ?)',
          (new_variant_id, api_data_id, new_name, response, False, timeout, operator),
        )
        variant_ids = _parse_response_variant_ids(target_row[0])
        variant_ids.append(new_variant_id)
        conn.execute(
          '''UPDATE api_data
             SET response_variant_ids=?,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE id = ?
          ''',
          (_normalize_response_variant_ids(variant_ids), api_data_id),
        )
      return {"success": True, "id": new_variant_id, "status_code": BIZ_SUCCESS, "status_msg": "成功"}
    except Exception as e:
      return {"success": False, "id": None, "status_code": BIZ_DB_ERROR, "status_msg": f"数据库操作失败: {str(e)}"}

  @_ensure_open(default={"success": False, "status_code": BIZ_UNKNOWN_ERROR, "status_msg": "绑定变体失败"})
  def bind_variants_to_api(self, api_data_id: str, variant_ids: List[str]) -> OperationResult:
    """直接替换 api_data 的变体 ID 绑定列表，失败返回 {"success": False, "status_code": 具体错误码, "status_msg": "具体错误信息"}"""
    if not api_data_id:
      return {"success": False, "status_code": BIZ_PARAM_MISSING, "status_msg": "缺少必填参数: api_data_id"}
    normalized = _normalize_response_variant_ids(variant_ids)
    try:
      with self._transaction() as conn:
        cursor = conn.execute(
          '''UPDATE api_data
             SET response_variant_ids=?,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE id = ?
          ''',
          (normalized, api_data_id),
        )
        return {"success": True, "status_code": BIZ_SUCCESS, "status_msg": "成功"}
    except Exception as e:
      return {"success": False, "status_code": BIZ_DB_ERROR, "status_msg": f"数据库操作失败: {str(e)}"}
