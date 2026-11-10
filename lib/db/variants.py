# -*- coding: utf-8 -*-
import sqlite3
import threading
from typing import Callable, ContextManager, List, Optional

from app_types.db_types import (
  ApiResponseVariant,
  ApiResponseVariantInsertRecord,
  ApiResponseVariantMeta,
  ApiResponseVariantRecord,
  OperationResult,
  OperationResultWithOptionalId,
  VariantQuery,
)
from config.enum import DATABASE
from config.enum.BIZ_CODE import (
  BIZ_DATA_NOT_FOUND,
  BIZ_DB_ERROR,
  BIZ_PARAM_MISSING,
  BIZ_UNKNOWN_ERROR,
)
from lib.logger_lib import DB_LOGGER
from lib.utils_lib import JsonFormat, generate_uuid

from .utils import (
  _ensure_open,
  _fail,
  _normalize_enabled,
  _normalize_response_variant_ids,
  _ok,
  _parse_enabled,
  _parse_response_variant_ids,
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
  _column_exists: Callable[[str, str], bool]
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
      DB_LOGGER.info('ApiResponseVariantMixin schema 迁移: v2 → v3, 新增 response 变体支持')
    if from_version < 4 <= to_version:
      # v3 → v4: api_response_variants 新增 operator 字段
      if not self._column_exists('api_response_variants', 'operator'):
        self._conn.execute("ALTER TABLE api_response_variants ADD COLUMN operator TEXT NOT NULL DEFAULT ''")
      DB_LOGGER.info('ApiResponseVariantMixin schema 迁移: v3 → v4, api_response_variants 新增 operator 字段')
    if from_version < 5 <= to_version:
      # v4 → v5: api_response_variants 新增 type 字段（创建来源类型，创建后不可变更）
      if not self._column_exists('api_response_variants', 'type'):
        self._conn.execute("ALTER TABLE api_response_variants ADD COLUMN type TEXT NOT NULL DEFAULT 'USER'")
      DB_LOGGER.info('ApiResponseVariantMixin schema 迁移: v4 → v5, api_response_variants 新增 type 字段')

  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "插入变体失败", id=None))
  def insert_variant(self, record: ApiResponseVariantInsertRecord) -> OperationResultWithOptionalId:
    """新增一条 response 变体，并自动追加到所属 api_data 的变体列表，成功返回 {"id": "uuid", "status_code": 0, "status_msg": "成功"}"""
    data = {**DATABASE.API_RESPONSE_VARIANT_INSERT_DEFAULTS, **record}
    variant_id = generate_uuid()
    api_data_id = data.get('api_data_id')
    if not api_data_id:
      DB_LOGGER.warning('ApiResponseVariantMixin insert_variant 缺少 api_data_id')
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: api_data_id", id=None)

    data['response'] = JsonFormat.format_json_string(data['response'])
    data['enabled'] = _normalize_enabled(data.get('enabled'))
    data['timeout'] = int(data.get('timeout', 0))

    try:
      with self._transaction() as conn:
        # 确认所属 api_data 存在，避免产生孤儿变体
        row = conn.execute('SELECT response_variant_ids FROM api_data WHERE id=?', (api_data_id,)).fetchone()
        if row is None:
          return _fail(BIZ_DATA_NOT_FOUND, f"关联的 API 数据不存在: {api_data_id}", id=None)
        conn.execute(
          'INSERT INTO api_response_variants (id, api_data_id, name, response, enabled, timeout, operator, type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
          (variant_id, api_data_id, data.get('name', ''), data['response'], data['enabled'], data['timeout'], data.get('operator', ''), data.get('type', 'USER')),
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
      return _ok(id=variant_id)
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}", id=None)

  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "更新变体失败"))
  def update_variant(self, record: ApiResponseVariantRecord) -> OperationResult:
    """按 id 更新变体（字段级合并），不允许修改所属 api_data_id，失败返回 {"status_code": 具体错误码, "status_msg": "具体错误信息"}"""
    variant_id = record.get('id')
    if not variant_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: id")

    with self._lock:
      row = self._conn.execute(
        'SELECT name, response, enabled, timeout, operator, type FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return _fail(BIZ_DATA_NOT_FOUND, f"记录不存在: {variant_id}")

    old = {
      'name': row[0],
      'response': row[1],
      'enabled': _parse_enabled(row[2]),
      'timeout': row[3],
      'operator': row[4],
      'type': row[5],
    }
    # api_data_id 和 type 不参与合并：api_data_id 防止破坏绑定关系，type 创建后不可变更
    merged = {**old, **{k: v for k, v in record.items() if k not in ('id', 'api_data_id', 'type') and v is not None}}
    merged['response'] = JsonFormat.format_json_string(merged['response'])
    merged['enabled'] = _normalize_enabled(merged.get('enabled'))
    merged['timeout'] = int(merged.get('timeout', 0))

    try:
      with self._transaction() as conn:
        conn.execute(
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
        return _ok()
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}")

  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "删除变体失败"))
  def delete_variant(self, variant_id: str) -> OperationResult:
    """按 id 删除变体，并同步从 api_data.response_variant_ids 中移除，失败返回 {"status_code": 具体错误码, "status_msg": "具体错误信息"}"""
    if not variant_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: id")

    with self._lock:
      row = self._conn.execute(
        'SELECT api_data_id FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return _fail(BIZ_DATA_NOT_FOUND, f"记录不存在: {variant_id}")
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
      return _ok()
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}")

  @_ensure_open(default=None)
  def get_variant_by_id(self, variant_id: str) -> Optional[ApiResponseVariant]:
    """按 id 主键查询单条变体，不存在时返回 None"""
    if not variant_id:
      return None
    with self._lock:
      row = self._conn.execute(
        'SELECT id, api_data_id, name, response, enabled, timeout, operator, type, created_at, updated_at FROM api_response_variants WHERE id=?',
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
      'type': row[7],
      'created_at': row[8],
      'updated_at': row[9],
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
    sql = 'SELECT id, api_data_id, name, response, enabled, timeout, operator, type, created_at, updated_at FROM api_response_variants WHERE api_data_id=?'
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
        'type': row[7],
        'created_at': row[8],
        'updated_at': row[9],
      })
    # 按 api_data.response_variant_ids 中的顺序排列，未在列表中的放最后
    result.sort(key=lambda v: order_map.get(v['id'], len(order_map)))
    return result

  # 按 api_data_id 批量查询变体轻量元数据（不加载 response 大文本）
  @_ensure_open(default=[])
  def get_variant_metas_by_api_ids(
      self,
      api_data_ids: List[str],
      enabled: Optional[bool] = None,
  ) -> List[ApiResponseVariantMeta]:
    """按 api_data_id 批量查询变体轻量元数据，供 mock 匹配映射构建使用

    enabled=None 返回全部，True 仅启用，False 仅禁用。
    不做排序，组内顺序由调用方按 api_data.response_variant_ids 自行排列。
    """
    if not api_data_ids:
      return []

    enabled_sql = ''
    if enabled is True:
      enabled_sql = ' AND enabled=1'
    elif enabled is False:
      enabled_sql = ' AND enabled=0'

    result: List[ApiResponseVariantMeta] = []
    # SQLite 变量上限安全分片（兼容旧版 SQLITE_MAX_VARIABLE_NUMBER=999）
    chunk_size = 500
    with self._lock:
      for i in range(0, len(api_data_ids), chunk_size):
        chunk = api_data_ids[i:i + chunk_size]
        placeholders = ','.join('?' * len(chunk))
        rows = self._conn.execute(
          f'SELECT id, api_data_id, timeout FROM api_response_variants WHERE api_data_id IN ({placeholders}){enabled_sql}',
          chunk,
        ).fetchall()
        for row in rows:
          result.append({'id': row[0], 'api_data_id': row[1], 'timeout': row[2]})
    return result

  def _build_variant_where(self, query: VariantQuery) -> tuple:
    """构建 api_response_variants 查询的 WHERE 子句和参数，返回 (where_sql, sql_params)"""
    where_clauses = []
    sql_params: list = []
    api_data_id = query.get('api_data_id')
    enabled = query.get('enabled')
    name_like = query.get('name_like')
    response_like = query.get('response_like')
    if api_data_id:
      where_clauses.append('api_data_id = ?')
      sql_params.append(api_data_id)
    if enabled is True:
      where_clauses.append('enabled = 1')
    elif enabled is False:
      where_clauses.append('enabled = 0')
    if name_like:
      where_clauses.append('name LIKE ?')
      sql_params.append(f'%{name_like}%')
    if response_like:
      where_clauses.append('response LIKE ?')
      sql_params.append(f'%{response_like}%')
    where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
    return where_sql, sql_params

  # 查询变体总数
  @_ensure_open(default=0)
  def get_variant_count(self, query: VariantQuery) -> int:
    """查询变体总数，支持 api_data_id 精确匹配、enabled 筛选、name/response 模糊查询"""
    where_sql, sql_params = self._build_variant_where(query)
    sql = f'SELECT COUNT(*) FROM api_response_variants{where_sql}'
    with self._lock:
      return self._conn.execute(sql, tuple(sql_params)).fetchone()[0]

  # 分页查询变体列表
  @_ensure_open(default=[])
  def get_variant_list_page(
      self,
      query: VariantQuery,
      reverse: bool = False,
      page_num: int = 1,
      page_size: int = 20,
  ) -> List[ApiResponseVariant]:
    """分页查询变体列表，返回完整记录（含 response），按 created_at 排序"""
    order = 'DESC, id DESC' if reverse else 'ASC, id ASC'
    offset = (page_num - 1) * page_size

    where_sql, sql_params = self._build_variant_where(query)
    sql = ('SELECT id, api_data_id, name, response, enabled, timeout, operator, type, created_at, updated_at '
           'FROM api_response_variants{} ORDER BY created_at {} LIMIT ? OFFSET ?').format(where_sql, order)
    sql_params.extend([page_size, offset])

    with self._lock:
      rows = self._conn.execute(sql, tuple(sql_params)).fetchall()
    result: List[ApiResponseVariant] = []
    for row in rows:
      result.append({
        'id': row[0],
        'api_data_id': row[1],
        'name': row[2],
        'response': row[3],
        'enabled': _parse_enabled(row[4]),
        'timeout': row[5],
        'operator': row[6],
        'type': row[7],
        'created_at': row[8],
        'updated_at': row[9],
      })
    return result

  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "复制变体失败", id=None))
  def copy_variant(
      self,
      variant_id: str,
      api_data_id: str,
      operator: str = '',
      variant_type: str = 'USER',
  ) -> OperationResultWithOptionalId:
    """复制一条 response 变体，并绑定到指定的 api_data 上。

    新变体的 enabled 固定为 False（默认不启用），不复制源变体的启用状态。
    副本的 type 和 operator 取当前操作者值（传入参数），不继承源变体的值。

    variant_id: 源变体 ID
    api_data_id: 目标 api_data ID（可以与源变体所属的 api_data 不同）
    operator: 当前操作者（如 'USER' / 'MCP'），作为副本的 operator 值
    variant_type: 当前操作者身份（如 'USER' / 'MCP'），作为副本的 type 值（创建后不可变更）

    返回：成功返回 {"id": "新变体ID", "status_code": 0, "status_msg": "成功"}，失败返回 {"id": None, "status_code": 具体错误码, "status_msg": "具体错误信息"}
    """
    if not variant_id or not api_data_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: variant_id 或 api_data_id", id=None)

    with self._lock:
      # 只取需要复制的业务字段，不取 operator/type（副本用当前操作者值）
      row = self._conn.execute(
        'SELECT name, response, timeout FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return _fail(BIZ_DATA_NOT_FOUND, f"源变体不存在: {variant_id}", id=None)

    name, response, timeout = row
    new_variant_id = generate_uuid()
    new_name = f'{name} (副本)' if name else '副本'

    try:
      with self._transaction() as conn:
        target_row = conn.execute(
          'SELECT response_variant_ids FROM api_data WHERE id=?', (api_data_id,)
        ).fetchone()
        if target_row is None:
          return _fail(BIZ_DATA_NOT_FOUND, f"目标 API 数据不存在: {api_data_id}", id=None)

        conn.execute(
          'INSERT INTO api_response_variants (id, api_data_id, name, response, enabled, timeout, operator, type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
          (new_variant_id, api_data_id, new_name, response, False, timeout, operator, variant_type),
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
      return _ok(id=new_variant_id)
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}", id=None)

  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "设为唯一启用失败"))
  def set_variant_exclusive_enabled(self, variant_id: str) -> OperationResult:
    """将指定变体设为启用，同时禁用同一 api_data_id 下的所有其他变体，失败返回 {"status_code": 具体错误码, "status_msg": "具体错误信息"}"""
    if not variant_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: id")

    with self._lock:
      row = self._conn.execute(
        'SELECT api_data_id FROM api_response_variants WHERE id=?',
        (variant_id,),
      ).fetchone()
    if row is None:
      return _fail(BIZ_DATA_NOT_FOUND, f"记录不存在: {variant_id}")
    api_data_id = row[0]

    try:
      with self._transaction() as conn:
        conn.execute(
          '''UPDATE api_response_variants
             SET enabled=0,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE api_data_id=? AND id!=?''',
          (api_data_id, variant_id),
        )
        conn.execute(
          '''UPDATE api_response_variants
             SET enabled=1,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE id=?''',
          (variant_id,),
        )
      return _ok()
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}")

  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "绑定变体失败"))
  def bind_variants_to_api(self, api_data_id: str, variant_ids: List[str]) -> OperationResult:
    """直接替换 api_data 的变体 ID 绑定列表，失败返回 {"status_code": 具体错误码, "status_msg": "具体错误信息"}"""
    if not api_data_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: api_data_id")
    normalized = _normalize_response_variant_ids(variant_ids)
    try:
      with self._transaction() as conn:
        conn.execute(
          '''UPDATE api_data
             SET response_variant_ids=?,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE id = ?
          ''',
          (normalized, api_data_id),
        )
        return _ok()
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}")
