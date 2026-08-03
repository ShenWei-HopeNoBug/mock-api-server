# -*- coding: utf-8 -*-
import json
import os
import sqlite3
import threading
import contextlib
import copy
import functools
from typing import Any, Callable, Dict, List, Optional
from importlib.resources import read_text
from lib.utils_lib import generate_uuid, JsonFormat
from lib.logger_lib import APP_LOGGER
from config.enum import DATABASE
from config.work_file import DB_DATA_PATH
from app_types.db_types import (
  ApiRecord,
  ApiData,
  ApiQuery,
  StaticData,
  ApiResponseVariantInsertRecord,
  ApiResponseVariantRecord,
  ApiResponseVariant,
)

# 当前 schema 版本
CURRENT_SCHEMA_VERSION = 3


def _normalize_response_variant_ids(value: Any) -> str:
  """把 List[str] 或 JSON 字符串统一格式化为标准 JSON 字符串，缺省时返回 '[]'"""
  if value is None:
    variant_ids: List[str] = []
  elif isinstance(value, str):
    try:
      parsed = json.loads(value)
      variant_ids = [str(v) for v in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
      variant_ids = []
  elif isinstance(value, list):
    variant_ids = [str(v) for v in value]
  else:
    variant_ids = []
  return JsonFormat.dumps(variant_ids)


def _parse_response_variant_ids(value: Any) -> List[str]:
  """从数据库 JSON 字符串解析为 List[str]，失败时返回空列表"""
  if not value:
    return []
  try:
    parsed = json.loads(value)
    return [str(v) for v in parsed] if isinstance(parsed, list) else []
  except (json.JSONDecodeError, TypeError):
    return []


def _normalize_enabled(value: Any) -> int:
  """把 bool/int/None 统一转为 0/1，None 时默认启用"""
  if value is None:
    return 1
  return 1 if value else 0


def _parse_enabled(value: Any) -> bool:
  """把数据库 0/1 转为 bool"""
  return bool(value)


def _ensure_open(default: Any = None):
  """DB 方法保护装饰器，DB 已关闭时返回 default 而非抛异常"""

  def decorator(method: Callable) -> Callable:
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
      if self._closed:
        APP_LOGGER.warning(f'{self.__class__.__name__} 已关闭，{method.__name__} 未执行')
        return copy.deepcopy(default)
      return method(self, *args, **kwargs)

    return wrapper

  return decorator


class BaseSQLiteDB:
  """
  SQLite 数据访问基类，封装与业务无关的基础设施

  提供连接管理、WAL 模式、事务控制、schema 版本管理等通用能力。
  子类通过 _schema_version 指定 schema 版本，通过 _migrate_schema 实现具体迁移逻辑。
  线程安全：通过 threading.Lock 保护所有读写操作。
  """

  # 子类覆盖：当前 schema 版本
  _schema_version: int = 1
  # 子类覆盖：schema 包名
  _schema_package: str = 'schema'

  def __init__(self, db_path: str):
    # 数据库文件路径
    self._db_path: str = db_path
    # 线程锁，保护所有读写操作
    self._lock: threading.Lock = threading.Lock()
    # SQLite 连接，允许跨线程访问
    self._conn: sqlite3.Connection = sqlite3.connect(db_path, check_same_thread=False)
    # 连接是否已关闭，用于 close() 幂等判断
    self._closed: bool = False
    # autocommit 模式，事务由代码显式控制
    self._conn.isolation_level = None
    # 跨进程锁竞争时等待 5s
    self._conn.execute('PRAGMA busy_timeout=5000')
    # WAL 模式
    self._conn.execute('PRAGMA journal_mode=WAL')
    # 建表（从 schema 包读取 .sql 文件）
    self._init_schema()
    # 启动时强制 checkpoint，清理上次异常退出可能残留的 -wal
    self._conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    # schema 版本管理
    self._check_schema_version()
    APP_LOGGER.info(f'{self.__class__.__name__} 初始化完成: {db_path}')

  def _init_schema(self) -> None:
    """从 schema 包读取 .sql 文件执行建表 DDL"""
    try:
      schema_sql = read_text(self._schema_package, f'v{self._schema_version}.sql')
      self._conn.executescript(schema_sql)
    except Exception as e:
      APP_LOGGER.error(f'{self.__class__.__name__} 建表失败 (schema v{self._schema_version}): {e}')
      raise

  def _migrate_schema(self, from_version: int, to_version: int) -> None:
    """schema 版本迁移，子类可 override 添加具体迁移逻辑"""
    self._conn.execute(f'PRAGMA user_version = {to_version}')

  def _check_schema_version(self) -> None:
    """检查数据库 schema 版本，首次写入版本号，降级时输出警告"""
    row = self._conn.execute('PRAGMA user_version').fetchone()
    db_version = row[0] if row else 0
    if db_version == 0:
      self._conn.execute(f'PRAGMA user_version = {self._schema_version}')
    elif db_version == self._schema_version:
      pass
    elif db_version < self._schema_version:
      self._migrate_schema(db_version, self._schema_version)
    else:
      APP_LOGGER.warning(
        f'{self.__class__.__name__} 数据库版本({db_version})比代码版本({self._schema_version})新，降级运行可能存在风险')

  # 执行 PASSIVE checkpoint，供批量写入后调用
  @_ensure_open()
  def _wal_checkpoint_passive(self) -> None:
    """执行 PASSIVE checkpoint，将 -wal 日志合并回主库"""
    with self._lock:
      self._conn.execute('PRAGMA wal_checkpoint(PASSIVE)')

  # 事务上下文管理器，自动处理 BEGIN/COMMIT/ROLLBACK 和线程锁
  @contextlib.contextmanager
  def _transaction(self):
    """
    事务上下文管理器

    自动处理 BEGIN/COMMIT/ROLLBACK 和线程锁。
    用法: with self._transaction() as conn: conn.execute(...)
    异常时自动 ROLLBACK 并记录日志。
    """
    with self._lock:
      conn = self._conn
      conn.execute('BEGIN TRANSACTION')
      try:
        yield conn
        conn.execute('COMMIT')
      except Exception as e:
        try:
          conn.execute('ROLLBACK')
        except Exception as rb_err:
          APP_LOGGER.error(f'{self.__class__.__name__} ROLLBACK 失败: {rb_err}')
        APP_LOGGER.error(f'{self.__class__.__name__} 事务回滚: {e}')
        raise

  # 关闭 DB 连接，触发 SQLite 自动 checkpoint
  def close(self) -> None:
    """关闭 DB 连接，触发 SQLite 自动 checkpoint，幂等可重复调用"""
    with self._lock:
      if not self._closed:
        self._conn.close()
        self._closed = True


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
      self._conn.execute('''
                         CREATE TABLE IF NOT EXISTS api_response_variants
                         (
                             id
                             TEXT
                             PRIMARY
                             KEY,
                             api_data_id
                             TEXT
                             NOT
                             NULL,
                             name
                             TEXT
                             NOT
                             NULL
                             DEFAULT
                             '',
                             response
                             TEXT
                             NOT
                             NULL
                             DEFAULT
                             '{}',
                             enabled
                             INTEGER
                             NOT
                             NULL
                             DEFAULT
                             1,
                             timeout
                             INTEGER
                             NOT
                             NULL
                             DEFAULT
                             0,
                             created_at
                             TEXT
                             NOT
                             NULL
                             DEFAULT (
                             strftime
                         (
                             '%Y-%m-%d %H:%M:%f',
                             'now',
                             'localtime'
                         )),
                             updated_at TEXT NOT NULL DEFAULT
                         (
                             strftime
                         (
                             '%Y-%m-%d %H:%M:%f',
                             'now',
                             'localtime'
                         ))
                             )
                         ''')
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
  def get_api_list(self, api_type: Optional[str] = None, reverse: bool = False) -> List[ApiData]:
    """查询 API 数据列表，可按 api_type 过滤、按时间正序/倒序排列"""
    order = 'DESC, id DESC' if reverse else 'ASC, id ASC'
    if api_type is not None:
      sql = f'SELECT id, type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type, created_at, updated_at FROM api_data WHERE type=? ORDER BY created_at {order}'
      params = (api_type,)
    else:
      sql = f'SELECT id, type, url, method, params, response, response_variant_ids, enabled, timeout, request_content_type, created_at, updated_at FROM api_data ORDER BY created_at {order}'
      params = ()
    with self._lock:
      cursor = self._conn.execute(sql, params)
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
    user_first = "CASE type WHEN 'USER' THEN 0 ELSE 1 END, " if query.get('api_type') is None else ''
    order_sql = 'ORDER BY {}created_at {}'.format(user_first, order)
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


class StaticDataMixin:
  """
  static_data 表的数据访问 Mixin

  提供 static_data 表的 CRUD 操作，依赖宿主类提供 _conn / _lock / _transaction 等基础设施。
  需与 BaseSQLiteDB 组合使用。
  """

  def _migrate_static(self, from_version: int, to_version: int) -> None:
    """static_data 表的 schema 版本迁移，逐版本升级"""
    if from_version < 3 <= to_version:
      # v2 → v3: 删除未使用的 idx_static_url 索引
      self._conn.execute('DROP INDEX IF EXISTS idx_static_url')
      APP_LOGGER.info('StaticDataMixin schema 迁移: v2 → v3, 删除未使用的 idx_static_url 索引')

  # 批量写静态资源到 DB
  @_ensure_open(default=False)
  def batch_insert_static(self, urls: List[str]) -> bool:
    """
    批量写入静态资源 URL，写入后触发 PASSIVE checkpoint

    纯 INSERT 不去重，id 统一用 generate_uuid 生成。
    返回 True 表示写入成功，False 表示空数据或写入异常。
    """
    if not urls:
      return False

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
      return True
    except Exception:
      return False
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
    params: List[Any] = [api_data_id]
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


class MockDB(BaseSQLiteDB, ApiDataMixin, StaticDataMixin, ApiResponseVariantMixin):
  """
  SQLite 数据访问层，封装 api_data / static_data / api_response_variants 的 CRUD 操作

  使用 WAL 模式 + autocommit，事务由 _transaction 上下文管理器显式控制。
  线程安全：通过 threading.Lock 保护所有读写操作。
  """

  _schema_version = CURRENT_SCHEMA_VERSION

  def _migrate_schema(self, from_version: int, to_version: int) -> None:
    """执行 schema 版本迁移，调度各 Mixin 的表级迁移逻辑"""
    self._migrate_api(from_version, to_version)
    self._migrate_static(from_version, to_version)
    super()._migrate_schema(from_version, to_version)


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
