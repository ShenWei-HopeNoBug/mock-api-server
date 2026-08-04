# -*- coding: utf-8 -*-
from typing import List, Optional

from lib.utils_lib import generate_uuid, JsonFormat
from lib.logger_lib import APP_LOGGER
from config.enum import DATABASE
from app_types.db_types import (
  ApiResponseVariantInsertRecord,
  ApiResponseVariantRecord,
  ApiResponseVariant,
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

  @_ensure_open(default=False)
  def insert_variant(self, record: ApiResponseVariantInsertRecord) -> bool:
    """新增一条 response 变体，并自动追加到所属 api_data 的变体列表，成功返回 True，失败返回 False"""
    data = {**DATABASE.API_RESPONSE_VARIANT_INSERT_DEFAULTS, **record}
    variant_id = generate_uuid()
    api_data_id = data.get('api_data_id')
    if not api_data_id:
      APP_LOGGER.warning('ApiResponseVariantMixin insert_variant 缺少 api_data_id')
      return False

    data['response'] = JsonFormat.format_json_string(data['response'])
    data['enabled'] = _normalize_enabled(data.get('enabled'))
    data['timeout'] = int(data.get('timeout', 0))

    try:
      with self._transaction() as conn:
        # 确认所属 api_data 存在，避免产生孤儿变体
        row = conn.execute('SELECT response_variant_ids FROM api_data WHERE id=?', (api_data_id,)).fetchone()
        if row is None:
          raise ValueError(f'api_data {api_data_id} 不存在')
        conn.execute(
          'INSERT INTO api_response_variants (id, api_data_id, name, response, enabled, timeout) VALUES (?, ?, ?, ?, ?, ?)',
          (variant_id, api_data_id, data.get('name', ''), data['response'], data['enabled'], data['timeout']),
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
      return True
    except Exception:
      return False

  @_ensure_open(default=False)
  def update_variant(self, record: ApiResponseVariantRecord) -> bool:
    """按 id 更新变体（字段级合并），不允许修改所属 api_data_id，失败返回 False"""
    variant_id = record.get('id')
    if not variant_id:
      return False

    with self._lock:
      row = self._conn.execute(
        'SELECT name, response, enabled, timeout FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return False

    old = {
      'name': row[0],
      'response': row[1],
      'enabled': _parse_enabled(row[2]),
      'timeout': row[3],
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
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE id = ?''',
          (merged['name'], merged['response'], merged['enabled'], merged['timeout'], variant_id),
        )
        return cursor.rowcount > 0
    except Exception:
      return False

  @_ensure_open(default=False)
  def delete_variant(self, variant_id: str) -> bool:
    """按 id 删除变体，并同步从 api_data.response_variant_ids 中移除，失败返回 False"""
    if not variant_id:
      return False

    with self._lock:
      row = self._conn.execute(
        'SELECT api_data_id FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return False
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
      return True
    except Exception:
      return False

  @_ensure_open(default=None)
  def get_variant_by_id(self, variant_id: str) -> Optional[ApiResponseVariant]:
    """按 id 主键查询单条变体，不存在时返回 None"""
    if not variant_id:
      return None
    with self._lock:
      row = self._conn.execute(
        'SELECT id, api_data_id, name, response, enabled, timeout, created_at, updated_at FROM api_response_variants WHERE id=?',
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
      'created_at': row[6],
      'updated_at': row[7],
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
    sql = 'SELECT id, api_data_id, name, response, enabled, timeout, created_at, updated_at FROM api_response_variants WHERE api_data_id=?'
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
        'created_at': row[6],
        'updated_at': row[7],
      })
    # 按 api_data.response_variant_ids 中的顺序排列，未在列表中的放最后
    result.sort(key=lambda v: order_map.get(v['id'], len(order_map)))
    return result

  @_ensure_open(default=False)
  def bind_variants_to_api(self, api_data_id: str, variant_ids: List[str]) -> bool:
    """直接替换 api_data 的变体 ID 绑定列表，失败返回 False"""
    if not api_data_id:
      return False
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
        return cursor.rowcount > 0
    except Exception:
      return False
