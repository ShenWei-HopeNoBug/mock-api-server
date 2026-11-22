# -*- coding: utf-8 -*-
import sqlite3
import threading
from typing import Callable, ContextManager, List, Optional

from app_types.db_types import (
  OperationResult,
  OperationResultWithOptionalId,
  TestGroupDetail,
  TestGroupQuery,
  TestGroupRecord,
  TestGroupSummary,
)
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


class TestGroupMixin:
  """
  test_group 表的数据访问 Mixin

  测试组 = 一组 mock 接口数据的命名集合：api_data.type='TEST_GROUP' 的行经 group_id 归属某组。
  全局至多一个组 enabled=1，启用/停用经 enable_test_group / disable_test_group 原子管理，
  不经 update_test_group 修改。
  需与 BaseSQLiteDB 组合使用。
  """

  # 基础设施属性声明（由宿主类 BaseSQLiteDB 提供，此处仅用于 IDE 类型提示）
  _conn: sqlite3.Connection
  _lock: threading.Lock
  _closed: bool
  _transaction: Callable[[], ContextManager[sqlite3.Connection]]
  _column_exists: Callable[[str, str], bool]
  _wal_checkpoint_passive: Callable[[], None]

  def _fetch_group_items(self, group_id: str) -> list:
    """Hook：获取组内 api_data 行列表，默认返回空列表，宿主类可覆写以注入真实实现

    get_test_group 需要关联查询组内接口条目，但 api_data 查询属于 ApiDataMixin
    的职责。与 _fetch_variants 同型的解耦 hook：
      - 默认实现返回空列表（安全降级，单独使用 TestGroupMixin 不会崩溃）
      - MockDB 作为组合根覆写此 hook，委托给 ApiDataMixin.get_api_list
    """
    return []

  def _migrate_test_group(self, from_version: int, to_version: int) -> None:
    """test_group 表的 schema 版本迁移，逐版本升级"""
    if from_version < 6 <= to_version:
      # v5 → v6: 新增 test_group 表（与 _migrate_variant 建表先例同型的幂等建表）
      # @formatter:off
      self._conn.execute(
        '''
          CREATE TABLE IF NOT EXISTS test_group (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL DEFAULT '',
            enabled    INTEGER NOT NULL DEFAULT 0,
            operator   TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
          )
        '''
      )
      # @formatter:on
      self._conn.execute('CREATE INDEX IF NOT EXISTS idx_test_group_enabled ON test_group(enabled)')
      DB_LOGGER.info('TestGroupMixin schema 迁移: v5 → v6, 新增 test_group 表')

  # 新建测试组，enabled 固定初始为 0（启用走 enable_test_group）
  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "创建测试组失败", id=None))
  def insert_test_group(self, record: TestGroupRecord) -> OperationResultWithOptionalId:
    """插入一条测试组记录，成功返回 {"id": "uuid", "status_code": 0, "status_msg": "成功"}"""
    group_id = generate_uuid()
    try:
      with self._transaction() as conn:
        conn.execute(
          'INSERT INTO test_group (id, name, enabled, operator) VALUES (?, ?, 0, ?)',
          (group_id, record.get('name', ''), record.get('operator', '')),
        )
      return _ok(id=group_id)
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}", id=None)

  # 按 id 更新测试组（字段级合并），仅 name/operator 可改
  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "更新测试组失败"))
  def update_test_group(self, record: TestGroupRecord) -> OperationResult:
    """字段级合并更新测试组；enabled 由 enable/disable 原子管理，不经此方法修改"""
    group_id = record.get('id')
    if not group_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: id")

    with self._lock:
      row = self._conn.execute('SELECT name, operator FROM test_group WHERE id=?', (group_id,)).fetchone()
    if row is None:
      return _fail(BIZ_DATA_NOT_FOUND, f"记录不存在: {group_id}")

    old = {'name': row[0], 'operator': row[1]}
    # 只放行 name/operator 参与合并，其余键（含 enabled）一律忽略
    merged = {**old, **{k: v for k, v in record.items() if k in ('name', 'operator') and v is not None}}

    try:
      with self._transaction() as conn:
        conn.execute(
          '''UPDATE test_group
             SET name=?,
                 operator=?,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE id = ?''',
          (merged['name'], merged['operator'], group_id),
        )
        return _ok()
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}")

  # 按 id 删除测试组，级联删除组内 api_data 行及其 response 变体
  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "删除测试组失败"))
  def delete_test_group(self, group_id: str) -> OperationResult:
    """级联删除：组内 api 的 variants → api_data WHERE group_id → test_group 行，同一事务原子完成"""
    if not group_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: group_id")

    with self._lock:
      row = self._conn.execute('SELECT id FROM test_group WHERE id=?', (group_id,)).fetchone()
    if row is None:
      return _fail(BIZ_DATA_NOT_FOUND, f"记录不存在: {group_id}")

    try:
      with self._transaction() as conn:
        rows = conn.execute('SELECT id FROM api_data WHERE group_id=?', (group_id,)).fetchall()
        api_ids = [r[0] for r in rows]
        if api_ids:
          placeholders = ','.join('?' * len(api_ids))
          conn.execute(f'DELETE FROM api_response_variants WHERE api_data_id IN ({placeholders})', api_ids)
          conn.execute('DELETE FROM api_data WHERE group_id=?', (group_id,))
        conn.execute('DELETE FROM test_group WHERE id=?', (group_id,))
        return _ok()
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}")

  # 按 id 查询测试组详情（组行字段 + 组内接口条目列表）
  @_ensure_open(default=None)
  def get_test_group(self, group_id: str) -> Optional[TestGroupDetail]:
    """查询测试组详情，items 经 _fetch_group_items hook 注入（MockDB 委托 get_api_list）"""
    if not group_id:
      return None
    with self._lock:
      row = self._conn.execute(
        'SELECT id, name, enabled, operator, created_at, updated_at FROM test_group WHERE id=?',
        (group_id,),
      ).fetchone()
    if row is None:
      return None

    items = self._fetch_group_items(group_id)
    result: TestGroupDetail = {
      'id': row[0],
      'name': row[1],
      'enabled': _parse_enabled(row[2]),
      'operator': row[3],
      'created_at': row[4],
      'updated_at': row[5],
      'items': items,
    }
    return result

  # 查询测试组列表（含组内 item 数），按创建时间倒序
  @_ensure_open(default=[])
  def get_test_group_list(self) -> List[TestGroupSummary]:
    """LEFT JOIN api_data 带出每组 item_count"""
    sql = '''
      SELECT g.id, g.name, g.enabled, g.operator, g.created_at, g.updated_at,
             COUNT(a.id) AS item_count
      FROM test_group g
      LEFT JOIN api_data a ON a.group_id = g.id
      GROUP BY g.id
      ORDER BY g.created_at DESC, g.id DESC
    '''
    with self._lock:
      rows = self._conn.execute(sql).fetchall()
    result: List[TestGroupSummary] = []
    for row in rows:
      result.append({
        'id': row[0],
        'name': row[1],
        'enabled': _parse_enabled(row[2]),
        'operator': row[3],
        'created_at': row[4],
        'updated_at': row[5],
        'item_count': row[6],
      })
    return result

  def _build_test_group_where(self, query: TestGroupQuery) -> tuple:
    """构建 test_group 查询的 WHERE 子句和参数，返回 (where_sql, sql_params)

    enabled 只做 True/False 过滤，多行 enabled=1 的不变量由 enable/disable 原子写保证。
    """
    where_clauses = []
    sql_params: list = []
    name_like = query.get('name_like')
    enabled = query.get('enabled')
    if name_like:
      where_clauses.append('g.name LIKE ?')
      sql_params.append(f'%{name_like}%')
    if enabled is True:
      where_clauses.append('g.enabled = 1')
    elif enabled is False:
      where_clauses.append('g.enabled = 0')
    where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
    return where_sql, sql_params

  # 按筛选条件查询测试组总数（count 不经 LEFT JOIN，where 字段均在 g 表）
  @_ensure_open(default=0)
  def get_test_group_count(self, query: TestGroupQuery) -> int:
    """查询符合条件的测试组总数，与 get_test_group_list_page 配套"""
    where_sql, sql_params = self._build_test_group_where(query)
    sql = f'SELECT COUNT(*) FROM test_group g{where_sql}'
    with self._lock:
      return self._conn.execute(sql, tuple(sql_params)).fetchone()[0]

  # 分页查询测试组列表（含组内 item 数），按创建时间倒序
  @_ensure_open(default=[])
  def get_test_group_list_page(
      self,
      query: TestGroupQuery,
      page_num: int = 1,
      page_size: int = 20,
  ) -> List[TestGroupSummary]:
    """分页查询测试组列表，支持 name 模糊查询、enabled 精确过滤"""
    offset = (page_num - 1) * page_size
    where_sql, sql_params = self._build_test_group_where(query)
    sql = '''
      SELECT g.id, g.name, g.enabled, g.operator, g.created_at, g.updated_at,
             COUNT(a.id) AS item_count
      FROM test_group g
      LEFT JOIN api_data a ON a.group_id = g.id
      {}
      GROUP BY g.id
      ORDER BY g.created_at DESC, g.id DESC
      LIMIT ? OFFSET ?
    '''.format(where_sql)
    sql_params.extend([page_size, offset])
    with self._lock:
      rows = self._conn.execute(sql, tuple(sql_params)).fetchall()
    result: List[TestGroupSummary] = []
    for row in rows:
      result.append({
        'id': row[0],
        'name': row[1],
        'enabled': _parse_enabled(row[2]),
        'operator': row[3],
        'created_at': row[4],
        'updated_at': row[5],
        'item_count': row[6],
      })
    return result

  # 查询当前启用的测试组摘要（含 item_count），无启用组返回 None
  @_ensure_open(default=None)
  def get_enabled_test_group_summary(self) -> Optional[TestGroupSummary]:
    """当前启用组单条摘要（全局至多一行 enabled=1），供页头指示"""
    sql = '''
      SELECT g.id, g.name, g.enabled, g.operator, g.created_at, g.updated_at,
             COUNT(a.id) AS item_count
      FROM test_group g
      LEFT JOIN api_data a ON a.group_id = g.id
      WHERE g.enabled = 1
      GROUP BY g.id
      LIMIT 1
    '''
    with self._lock:
      row = self._conn.execute(sql).fetchone()
    if row is None:
      return None
    return {
      'id': row[0],
      'name': row[1],
      'enabled': _parse_enabled(row[2]),
      'operator': row[3],
      'created_at': row[4],
      'updated_at': row[5],
      'item_count': row[6],
    }

  # 查询当前启用的测试组 id（全局至多一个），mock 子进程每请求调用
  @_ensure_open(default=None)
  def get_enabled_test_group_id(self) -> Optional[str]:
    """SELECT id WHERE enabled=1，无启用组返回 None"""
    with self._lock:
      row = self._conn.execute('SELECT id FROM test_group WHERE enabled=1 LIMIT 1').fetchone()
    return row[0] if row else None

  # 启用指定测试组（原子顶替：同事务先清全部启用态再置目标）
  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "启用测试组失败"))
  def enable_test_group(self, group_id: str) -> OperationResult:
    """一事务 enabled=0 全清 + enabled=1 置目标，保证全局至多一行启用"""
    if not group_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: group_id")

    with self._lock:
      row = self._conn.execute('SELECT id FROM test_group WHERE id=?', (group_id,)).fetchone()
    if row is None:
      return _fail(BIZ_DATA_NOT_FOUND, f"记录不存在: {group_id}")

    try:
      with self._transaction() as conn:
        conn.execute(
          '''UPDATE test_group
             SET enabled=0,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE enabled=1''',
        )
        conn.execute(
          '''UPDATE test_group
             SET enabled=1,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE id=?''',
          (group_id,),
        )
      return _ok()
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}")

  # 停用全部测试组（无参清启用态）
  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "停用测试组失败"))
  def disable_test_group(self) -> OperationResult:
    """UPDATE test_group SET enabled=0 全清；顺带修复「多行 enabled=1」的不变量破损"""
    try:
      with self._transaction() as conn:
        conn.execute(
          '''UPDATE test_group
             SET enabled=0,
                 updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
             WHERE enabled=1''',
        )
      return _ok()
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}")

  # 把一条已有 api_data 拷入测试组（生成 type='TEST_GROUP' 的组内副本）
  @_ensure_open(default=_fail(BIZ_UNKNOWN_ERROR, "拷入测试组失败", id=None))
  def copy_api_to_group(
      self,
      api_id: str,
      group_id: str,
      copy_variants: bool = True,
      enabled: bool = True,
      operator: str = '',
  ) -> OperationResultWithOptionalId:
    """复制一条 API 数据为组内副本，返回新条目 id。

    - 副本 type='TEST_GROUP'、group_id 指向目标组（创建后不可变），operator 记当前操作者
    - enabled 由入参决定（调用方按入口语义传默认值：outputManager 推入 False / 组详情拉取 True）
    - copy_variants=True 时按源 response_variant_ids 顺序拷贝变体行：保留源 enabled 态
      （场景快照需要确定性状态），type/operator 记当前操作者，name 保持原名不追加后缀
    - 源数据不变；同 key 冲突按「后者覆盖前者」的建图语义处理，拷贝时不做校验
    """
    if not api_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: api_id", id=None)
    if not group_id:
      return _fail(BIZ_PARAM_MISSING, "缺少必填参数: group_id", id=None)

    with self._lock:
      group_row = self._conn.execute('SELECT id FROM test_group WHERE id=?', (group_id,)).fetchone()
      if group_row is None:
        return _fail(BIZ_DATA_NOT_FOUND, f"目标测试组不存在: {group_id}", id=None)
      src = self._conn.execute(
        'SELECT url, method, params, response, response_variant_ids, timeout, request_content_type FROM api_data WHERE id=?',
        (api_id,),
      ).fetchone()
    if src is None:
      return _fail(BIZ_DATA_NOT_FOUND, f"源 API 数据不存在: {api_id}", id=None)

    url, method, params, response, src_variant_ids_raw, timeout, request_content_type = src
    new_api_id = generate_uuid()
    new_variant_ids: List[str] = []
    variant_type = operator or 'USER'

    try:
      with self._transaction() as conn:
        # 按源绑定顺序逐个拷贝变体，保留 enabled 态（场景快照语义）
        if copy_variants:
          for variant_id in _parse_response_variant_ids(src_variant_ids_raw):
            vrow = conn.execute(
              'SELECT name, response, enabled, timeout FROM api_response_variants WHERE id=?',
              (variant_id,),
            ).fetchone()
            if vrow is None:
              continue
            new_variant_id = generate_uuid()
            conn.execute(
              'INSERT INTO api_response_variants (id, api_data_id, name, response, enabled, timeout, operator, type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
              (new_variant_id, new_api_id, vrow[0], vrow[1], vrow[2], vrow[3], operator, variant_type),
            )
            new_variant_ids.append(new_variant_id)
        conn.execute(
          'INSERT INTO api_data (id, type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type, operator, group_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
          (new_api_id, 'TEST_GROUP', url, method,
           JsonFormat.format_json_string(params), response,
           _normalize_response_variant_ids(new_variant_ids), _normalize_enabled(enabled),
           timeout, request_content_type, operator, group_id),
        )
      return _ok(id=new_api_id)
    except Exception as e:
      return _fail(BIZ_DB_ERROR, f"数据库操作失败: {str(e)}", id=None)
