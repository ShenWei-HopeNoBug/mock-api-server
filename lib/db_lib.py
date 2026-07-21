# -*- coding: utf-8 -*-
import sqlite3
import threading
import contextlib
from typing import List
from importlib.resources import read_text
from lib.utils_lib import generate_uuid, JsonFormat
from lib.logger_lib import APP_LOGGER
from config.enum import DATABASE
from types.db_types import ApiRecord, ApiData, StaticData

# 当前 schema 版本
CURRENT_SCHEMA_VERSION = 1


class MockDB:
  """
  SQLite 数据访问层，封装所有 DB 读写操作

  使用 WAL 模式 + autocommit，事务由 _transaction 上下文管理器显式控制。
  线程安全：通过 threading.Lock 保护所有读写操作。
  """

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
    APP_LOGGER.info(f'MockDB 初始化完成: {db_path}')

  def _init_schema(self):
    """从 schema 包读取 .sql 文件执行建表 DDL"""
    try:
      schema_sql = read_text('schema', f'v{CURRENT_SCHEMA_VERSION}.sql')
      self._conn.executescript(schema_sql)
    except Exception as e:
      APP_LOGGER.error(f'MockDB 建表失败 (schema v{CURRENT_SCHEMA_VERSION}): {e}')
      raise

  def _check_schema_version(self):
    """检查数据库 schema 版本，首次写入版本号，降级时输出警告"""
    row = self._conn.execute('PRAGMA user_version').fetchone()
    db_version = row[0] if row else 0
    if db_version == 0:
      self._conn.execute(f'PRAGMA user_version = {CURRENT_SCHEMA_VERSION}')
    elif db_version == CURRENT_SCHEMA_VERSION:
      pass
    elif db_version < CURRENT_SCHEMA_VERSION:
      pass
    else:
      APP_LOGGER.warning(f'MockDB 数据库版本({db_version})比代码版本({CURRENT_SCHEMA_VERSION})新，降级运行可能存在风险')

  # 执行 PASSIVE checkpoint，供批量写入后调用
  def _wal_checkpoint_passive(self):
    """执行 PASSIVE checkpoint，将 -wal 日志合并回主库"""
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
        conn.execute('ROLLBACK')
        APP_LOGGER.error(f'MockDB 事务回滚: {e}')
        raise

  # 新增插入（纯 INSERT，不去重），返回生成的 id
  def upsert_api(self, record: ApiRecord) -> str:
    """插入一条 API 数据，返回生成的 id"""
    api_id = generate_uuid()
    data = {**DATABASE.API_INSERT_DEFAULTS, **record}
    data['params'] = JsonFormat.format_json_string(data['params'])
    with self._transaction() as conn:
      conn.execute(
        'INSERT INTO api_data (id, type, url, method, params, response) VALUES (?, ?, ?, ?, ?, ?)',
        (api_id, data['type'], data['url'], data['method'], data['params'], data['response']),
      )
    return api_id

  # 批量写入 API 数据到 DB
  def batch_insert_api(self, records: List[ApiRecord]) -> None:
    """
    批量插入 API 数据，写入后触发 PASSIVE checkpoint

    不判断 id 是否重复，全部走 INSERT。重复数据的判断由应用层自行处理。
    id 统一用 generate_uuid 生成，字段缺失时用 API_INSERT_DEFAULTS 兜底，params 做 JSON 格式化。
    """
    if not records:
      return

    insert_sql = 'INSERT INTO api_data (id, type, url, method, params, response) VALUES (?, ?, ?, ?, ?, ?)'
    insert_data = []
    for r in records:
      api_id = generate_uuid()
      data = {**DATABASE.API_INSERT_DEFAULTS, **r}
      data['id'] = api_id
      data['params'] = JsonFormat.format_json_string(data['params'])
      insert_data.append((api_id, data['type'], data['url'], data['method'], data['params'], data['response']))

    try:
      with self._transaction() as conn:
        conn.executemany(insert_sql, insert_data)
      APP_LOGGER.info(f'MockDB batch_insert_api 写入 {len(records)} 条')
    finally:
      self._wal_checkpoint_passive()

  # 查询 api 数据列表
  def get_api_list(self, type: str = None, reverse: bool = False) -> List[ApiData]:
    """查询 API 数据列表，可按 type 过滤、按时间正序/倒序排列"""
    order = 'DESC, id DESC' if reverse else 'ASC, id ASC'
    if type is not None:
      sql = f'SELECT id, type, url, method, params, response, created_at, updated_at FROM api_data WHERE type=? ORDER BY created_at {order}'
      params = (type,)
    else:
      sql = f'SELECT id, type, url, method, params, response, created_at, updated_at FROM api_data ORDER BY created_at {order}'
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
        'created_at': row[6],
        'updated_at': row[7],
      })
    return result

  # 按 id 更新 api 数据（字段级合并）
  def update_api(self, record: ApiRecord) -> bool:
    """
    按 id 更新 API 数据，字段级合并

    前端只传修改的字段时旧值保留，记录不存在时返回 False。
    """
    with self._transaction() as conn:
      # 1. 查询旧记录
      row = conn.execute(
        'SELECT type, url, method, params, response FROM api_data WHERE id=?',
        (record.get('id'),),
      ).fetchone()
      if row is None:
        return False

      # 2. 字段级合并：record 中非空字段覆盖旧值，id 仅作 WHERE 条件不参与合并
      old = {
        'type': row[0],
        'url': row[1],
        'method': row[2],
        'params': row[3],
        'response': row[4],
      }
      merged = {**old, **{k: v for k, v in record.items() if k != 'id' and v}}

      # 3. 写入合并后的完整记录
      conn.execute(
        '''UPDATE api_data
           SET type=?,
               url=?,
               method=?,
               params=?,
               response=?,
               updated_at=strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
           WHERE id = ?''',
        (merged['type'], merged['url'], merged['method'],
         merged['params'], merged['response'], record.get('id')),
      )
      return True

  # 按 id 删除 api 数据
  def delete_api(self, api_id: str) -> bool:
    """按 id 删除 API 数据，记录不存在时返回 False"""
    with self._transaction() as conn:
      cursor = conn.execute('DELETE FROM api_data WHERE id=?', (api_id,))
      if cursor.rowcount == 0:
        return False
      return True

  # 批量写静态资源到 DB
  def batch_upsert_static(self, records: list) -> None:
    """批量写入静态资源 URL，按 url 做 UPSERT，写入后触发 PASSIVE checkpoint"""
    if not records:
      return
    sql = '''
          INSERT INTO static_data (url, type)
          VALUES (?, 'MITMPROXY') ON CONFLICT(url) DO
          UPDATE SET updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime') \
          '''
    data = [(url,) for url in records]
    try:
      with self._transaction() as conn:
        conn.executemany(sql, data)
      APP_LOGGER.info(f'MockDB batch_upsert_static 写入 {len(records)} 条')
    finally:
      self._wal_checkpoint_passive()

  # 查静态资源列表
  def get_static_list(self) -> List[StaticData]:
    """查询全部静态资源列表，按创建时间倒序排列"""
    sql = 'SELECT url, type, created_at, updated_at FROM static_data ORDER BY created_at DESC, url DESC'
    with self._lock:
      cursor = self._conn.execute(sql)
      rows = cursor.fetchall()
    result = []
    for row in rows:
      result.append({
        'url': row[0],
        'type': row[1],
        'created_at': row[2],
        'updated_at': row[3],
      })
    return result

  # 关闭 DB 连接，触发 SQLite 自动 checkpoint
  def close(self):
    """关闭 DB 连接，触发 SQLite 自动 checkpoint，幂等可重复调用"""
    with self._lock:
      if not self._closed:
        self._conn.close()
        self._closed = True
