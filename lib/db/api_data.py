# -*- coding: utf-8 -*-
from typing import List, Optional

from lib.utils_lib import generate_uuid, JsonFormat
from lib.logger_lib import APP_LOGGER
from config.enum import DATABASE
from app_types.db_types import (
  ApiRecord,
  ApiQuery,
  ApiData,
)
from .utils import (
  _ensure_open,
  _normalize_response_variant_ids,
  _parse_response_variant_ids,
  _normalize_enabled,
  _parse_enabled,
)


class ApiDataMixin:
  """
  api_data 表的数据访问 Mixin

  提供 api_data 表的 CRUD 操作，依赖宿主类提供 _conn / _lock / _transaction 等基础设施。
  需与 BaseSQLiteDB 组合使用。
  """

  def _migrate_api(self, from_version: int, to_version: int) -> None:
    """api_data 表的 schema 版本迁移，逐版本升级"""
    if from_version < 2 <= to_version:
      # v1 → v2: api_data 新增 timeout 字段
      self._conn.execute('ALTER TABLE api_data ADD COLUMN timeout INTEGER NOT NULL DEFAULT 0')
      # v1 → v2: api_data 新增 request_content_type 字段
      self._conn.execute("ALTER TABLE api_data ADD COLUMN request_content_type TEXT NOT NULL DEFAULT 'NONE'")
      APP_LOGGER.info('ApiDataMixin schema 迁移: v1 → v2, api_data 新增 timeout 和 request_content_type 字段')
    if from_version < 3 <= to_version:
      # v2 → v3: api_data 新增 response_variant_ids 与 enabled 字段
      self._conn.execute("ALTER TABLE api_data ADD COLUMN response_variant_ids TEXT NOT NULL DEFAULT '[]'")
      self._conn.execute('ALTER TABLE api_data ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1')
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
      APP_LOGGER.info('ApiDataMixin schema 迁移: v2 → v3, 新增 response 变体支持')

  # 新增插入（纯 INSERT，不去重），返回是否成功
  @_ensure_open(default=False)
  def insert_api(self, record: ApiRecord) -> bool:
    """插入一条 API 数据，成功返回 True，失败返回 False"""
    api_id = generate_uuid()
    data = {**DATABASE.API_INSERT_DEFAULTS, **record}
    data['params'] = JsonFormat.format_json_string(data['params'])
    data['response_variant_ids'] = _normalize_response_variant_ids(data.get('response_variant_ids'))
    data['enabled'] = _normalize_enabled(data.get('enabled'))
    try:
      with self._transaction() as conn:
        conn.execute(
          'INSERT INTO api_data (id, type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
          (api_id, data['type'], data['url'], data['method'], data['params'], data['response'],
           data['response_variant_ids'], data['enabled'], data.get('timeout', 0),
           data.get('request_content_type', 'NONE')),
        )
      return True
    except Exception:
      return False

  # 批量写入 API 数据到 DB
  @_ensure_open(default=False)
  def batch_insert_api(self, records: List[ApiRecord]) -> bool:
    """
    批量插入 API 数据，写入后触发 PASSIVE checkpoint

    不判断 id 是否重复，全部走 INSERT。重复数据的判断由应用层自行处理。
    id 统一用 generate_uuid 生成，字段缺失时用 API_INSERT_DEFAULTS 兜底，params 做 JSON 格式化。
    返回 True 表示写入成功，False 表示空数据或写入异常。
    """
    if not records:
      return False

    insert_sql = 'INSERT INTO api_data (id, type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    insert_data = []
    for r in records:
      api_id = generate_uuid()
      data = {**DATABASE.API_INSERT_DEFAULTS, **r}
      data['id'] = api_id
      data['params'] = JsonFormat.format_json_string(data['params'])
      data['response_variant_ids'] = _normalize_response_variant_ids(data.get('response_variant_ids'))
      data['enabled'] = _normalize_enabled(data.get('enabled'))
      insert_data.append(
        (api_id, data['type'], data['url'], data['method'], data['params'], data['response'],
         data['response_variant_ids'], data['enabled'], data.get('timeout', 0),
         data.get('request_content_type', 'NONE')))

    try:
      with self._transaction() as conn:
        conn.executemany(insert_sql, insert_data)
      APP_LOGGER.info(f'MockDB batch_insert_api 写入 {len(records)} 条')
      return True
    except Exception:
      return False
    finally:
      try:
        self._wal_checkpoint_passive()
      except Exception as e:
        APP_LOGGER.error(f'MockDB batch_insert_api checkpoint 失败: {e}')

  # 查询 api 数据列表
  @_ensure_open(default=[])
  def get_api_list(
      self,
      query: Optional[ApiQuery] = None,
      reverse: bool = False,
  ) -> List[ApiData]:
    """查询 API 数据列表，支持 ApiQuery 全部筛选条件，按时间正序/倒序排列"""
    if query is None:
      query = ApiQuery()

    order = 'DESC, id DESC' if reverse else 'ASC, id ASC'
    where_sql, sql_params = self._build_api_where(query)
    order_sql = 'ORDER BY created_at {}'.format(order)
    sql = 'SELECT id, type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type, created_at, updated_at FROM api_data{} {}'.format(
      where_sql, order_sql)

    with self._lock:
      cursor = self._conn.execute(sql, tuple(sql_params))
      rows = cursor.fetchall()
    result = []
    for row in rows:
      result.append({
        'id': row[0],
        'type': row[1],
        'url': row[2],
        'method': row[3],
        'params': row[4],
        'response': row[5],
        'response_variant_ids': _parse_response_variant_ids(row[6]),
        'enabled': _parse_enabled(row[7]),
        'timeout': row[8],
        'request_content_type': row[9],
        'created_at': row[10],
        'updated_at': row[11],
      })
    return result

  def _build_api_where(self, query: ApiQuery) -> tuple:
    """构建 api_data 查询的 WHERE 子句和参数，返回 (where_sql, sql_params)"""
    where_clauses = []
    sql_params: list = []
    api_type = query.get('api_type')
    url_like = query.get('url_like')
    params_like = query.get('params_like')
    response_like = query.get('response_like')
    method = query.get('method')
    request_content_type = query.get('request_content_type')
    enabled = query.get('enabled')
    create_start_time = query.get('create_start_time')
    create_end_time = query.get('create_end_time')
    if api_type is not None:
      where_clauses.append('type = ?')
      sql_params.append(api_type)
    if url_like:
      where_clauses.append('url LIKE ?')
      sql_params.append(f'%{url_like}%')
    if params_like:
      where_clauses.append('params LIKE ?')
      sql_params.append(f'%{params_like}%')
    if response_like:
      where_clauses.append('response LIKE ?')
      sql_params.append(f'%{response_like}%')
    if method:
      where_clauses.append('method = ?')
      sql_params.append(method)
    if request_content_type:
      where_clauses.append('request_content_type = ?')
      sql_params.append(request_content_type)
    if enabled is True:
      where_clauses.append('enabled = 1')
    elif enabled is False:
      where_clauses.append('enabled = 0')
    if create_start_time and create_end_time:
      where_clauses.append('datetime(created_at) >= datetime(?)')
      sql_params.append(create_start_time)
      where_clauses.append('datetime(created_at) <= datetime(?)')
      sql_params.append(create_end_time)
    where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
    return where_sql, sql_params

  # 分页查询 api 数据列表
  @_ensure_open(default=[])
  def get_api_list_page(
      self,
      query: ApiQuery,
      reverse: bool = False,
      page_num: int = 1,
      page_size: int = 20,
  ) -> List[ApiData]:
    """分页查询 API 数据列表，支持 url/params/response 模糊查询、method 精确查询、created_at 时间区间查询"""
    order = 'DESC, id DESC' if reverse else 'ASC, id ASC'
    offset = (page_num - 1) * page_size

    where_sql, sql_params = self._build_api_where(query)
    order_sql = 'ORDER BY created_at {}'.format(order)
    sql = 'SELECT id, type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type, created_at, updated_at FROM api_data{} {} LIMIT ? OFFSET ?'.format(
      where_sql, order_sql)
    sql_params.extend([page_size, offset])

    with self._lock:
      cursor = self._conn.execute(sql, tuple(sql_params))
      rows = cursor.fetchall()
    result = []
    for row in rows:
      result.append({
        'id': row[0],
        'type': row[1],
        'url': row[2],
        'method': row[3],
        'params': row[4],
        'response': row[5],
        'response_variant_ids': _parse_response_variant_ids(row[6]),
        'enabled': _parse_enabled(row[7]),
        'timeout': row[8],
        'request_content_type': row[9],
        'created_at': row[10],
        'updated_at': row[11],
      })
    return result

  # 查询 api 数据总数
  @_ensure_open(default=0)
  def get_api_count(self, query: ApiQuery) -> int:
    """查询 API 数据总数，支持 url/params/response 模糊查询、method 精确查询、created_at 时间区间查询"""
    where_sql, sql_params = self._build_api_where(query)
    sql = f'SELECT COUNT(*) FROM api_data{where_sql}'
    with self._lock:
      return self._conn.execute(sql, tuple(sql_params)).fetchone()[0]

  # 按 id 查询单条 api 数据
  @_ensure_open(default=None)
  def get_api_by_id(self, api_id: str) -> Optional[ApiData]:
    """按 id 主键查询单条 API 数据，不存在时返回 None"""
    if not api_id:
      return None
    with self._lock:
      row = self._conn.execute(
        'SELECT id, type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type, created_at, updated_at FROM api_data WHERE id=?',
        (api_id,),
      ).fetchone()
    if row is None:
      return None

    result: ApiData = {
      'id': row[0],
      'type': row[1],
      'url': row[2],
      'method': row[3],
      'params': row[4],
      'response': row[5],
      'response_variant_ids': _parse_response_variant_ids(row[6]),
      'enabled': _parse_enabled(row[7]),
      'timeout': row[8],
      'request_content_type': row[9],
      'created_at': row[10],
      'updated_at': row[11],
    }

    return result

  # 按 id 更新 api 数据（字段级合并）
  @_ensure_open(default=False)
  def update_api(self, record: ApiRecord) -> bool:
    """
    按 id 更新 API 数据，字段级合并

    前端只传修改的字段时旧值保留，记录不存在时返回 False。
    """
    api_id = record.get('id')
    if not api_id:
      return False

    # 1. 事务外查询旧记录，不存在则直接返回，避免空事务
    with self._lock:
      row = self._conn.execute(
        'SELECT type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type FROM api_data WHERE id=?',
        (api_id,),
      ).fetchone()
    if row is None:
      return False

    with self._transaction() as conn:
      # 2. 字段级合并：record 中非空字段覆盖旧值，id 仅作 WHERE 条件不参与合并
      old = {
        'type': row[0],
        'url': row[1],
        'method': row[2],
        'params': row[3],
        'response': row[4],
        'response_variant_ids': row[5],
        'enabled': row[6],
        'timeout': row[7],
        'request_content_type': row[8],
      }
      merged = {**old, **{k: v for k, v in record.items() if k != 'id' and v is not None}}
      merged['params'] = JsonFormat.format_json_string(merged['params'])
      merged['response_variant_ids'] = _normalize_response_variant_ids(merged.get('response_variant_ids'))
      merged['enabled'] = _normalize_enabled(merged.get('enabled'))

      # 3. 写入合并后的完整记录
      cursor = conn.execute(
        '''UPDATE api_data
           SET type=?,
               url=?,
               method=?,
               params=?,
               response=?,
               response_variant_ids=?,
               enabled=?,
               timeout=?,
               request_content_type=?,
               updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
           WHERE id = ?''',
        (merged['type'], merged['url'], merged['method'],
         merged['params'], merged['response'], merged['response_variant_ids'], merged['enabled'],
         merged.get('timeout', 0), merged.get('request_content_type', 'NONE'), api_id),
      )
      if cursor.rowcount == 0:
        return False
      return True

  # 按 id 删除 api 数据
  @_ensure_open(default=False)
  def delete_api(self, api_id: str) -> bool:
    """按 id 删除 API 数据，同时级联删除其 response 变体，记录不存在时返回 False"""
    if not api_id:
      return False
    with self._transaction() as conn:
      conn.execute('DELETE FROM api_response_variants WHERE api_data_id=?', (api_id,))
      cursor = conn.execute('DELETE FROM api_data WHERE id=?', (api_id,))
      if cursor.rowcount == 0:
        return False
      return True

  # 批量删除 api 数据（按 ApiQuery 筛选条件，与 get_api_list_page 一致）
  @_ensure_open(default=False)
  def batch_delete_api(self, query: ApiQuery) -> bool:
    """
    批量删除 API 数据，筛选条件与 get_api_list_page 完全一致

    支持 api_type 精确匹配、url/params/response 模糊查询、method 精确查询、created_at 时间区间查询。
    没有任何筛选条件时拒绝执行（防止全表删除），返回 False。
    删除成功（含 0 条匹配）返回 True，异常返回 False。
    """
    where_sql, sql_params = self._build_api_where(query)
    if not where_sql:
      APP_LOGGER.warning('MockDB batch_delete_api 拒绝执行：未提供有效筛选条件')
      return False

    try:
      with self._transaction() as conn:
        # 先查出要删除的 api_data id，再级联删除其变体
        rows = conn.execute(f'SELECT id FROM api_data{where_sql}', tuple(sql_params)).fetchall()
        api_ids = [row[0] for row in rows]
        if api_ids:
          placeholders = ','.join('?' * len(api_ids))
          conn.execute(f'DELETE FROM api_response_variants WHERE api_data_id IN ({placeholders})', api_ids)
        cursor = conn.execute(f'DELETE FROM api_data{where_sql}', tuple(sql_params))
      APP_LOGGER.info(f'MockDB batch_delete_api 删除 {cursor.rowcount} 条')
      return True
    except Exception:
      return False
