# -*- coding: utf-8 -*-
import sqlite3
import threading
from lib.utils_lib import generate_uuid, JsonFormat

# 当前 schema 版本
CURRENT_SCHEMA_VERSION = 1


class MockDB:
  # SQLite 数据访问层，封装所有 DB 读写操作
  def __init__(self, db_path: str):
    self._db_path = db_path
    self._lock = threading.Lock()
    self._conn = sqlite3.connect(db_path, check_same_thread=False)
    # autocommit 模式，事务由代码显式控制
    self._conn.isolation_level = None
    # 跨进程锁竞争时等待 5s
    self._conn.execute('PRAGMA busy_timeout=5000')
    # WAL 模式
    self._conn.execute('PRAGMA journal_mode=WAL')
    # 建表
    self._conn.execute('''
      CREATE TABLE IF NOT EXISTS api_data (
        id             TEXT PRIMARY KEY,
        type           TEXT NOT NULL DEFAULT 'MITMPROXY',
        url            TEXT NOT NULL DEFAULT '',
        method         TEXT NOT NULL DEFAULT 'GET',
        params         TEXT NOT NULL DEFAULT '{}',
        response       TEXT NOT NULL DEFAULT '{}',
        created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
        updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
      )
    ''')
    self._conn.execute('CREATE INDEX IF NOT EXISTS idx_api_type ON api_data(type)')
    self._conn.execute('''
      CREATE TABLE IF NOT EXISTS static_data (
        url         TEXT PRIMARY KEY,
        type        TEXT NOT NULL DEFAULT 'MITMPROXY',
        created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
        updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
      )
    ''')
    # 启动时强制 checkpoint，清理上次异常退出可能残留的 -wal
    self._conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    # schema 版本管理
    self._check_schema_version()

  def _check_schema_version(self):
    row = self._conn.execute('PRAGMA user_version').fetchone()
    db_version = row[0] if row else 0
    if db_version == 0:
      self._conn.execute(f'PRAGMA user_version = {CURRENT_SCHEMA_VERSION}')
    elif db_version == CURRENT_SCHEMA_VERSION:
      pass
    elif db_version < CURRENT_SCHEMA_VERSION:
      pass
    else:
      print(f'@@MockDB: 数据库版本({db_version})比代码版本({CURRENT_SCHEMA_VERSION})新，降级运行可能存在风险')

  # 执行 PASSIVE checkpoint，供批量写入后调用
  def _wal_checkpoint_passive(self):
    self._conn.execute('PRAGMA wal_checkpoint(PASSIVE)')

  # 新增插入（纯 INSERT，不去重），返回生成的 id
  def upsert_api(self, record: dict) -> str:
    api_id = generate_uuid()
    type_ = record.get('type', 'USER')
    url = record.get('url', '')
    method = record.get('method', 'GET')
    params = JsonFormat.format_json_string(record.get('params', '{}'))
    response = record.get('response', '{}')
    with self._lock:
      conn = self._conn
      conn.execute('BEGIN TRANSACTION')
      try:
        conn.execute(
          'INSERT INTO api_data (id, type, url, method, params, response) VALUES (?, ?, ?, ?, ?, ?)',
          (api_id, type_, url, method, params, response),
        )
        conn.execute('COMMIT')
      except Exception:
        conn.execute('ROLLBACK')
        raise
    return api_id

  # 批量写入抓包数据到 DB
  def batch_upsert_api(self, records: list) -> None:
    if not records:
      return
    sql = '''
      INSERT INTO api_data (id, type, url, method, params, response)
      VALUES (?, 'MITMPROXY', ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        url=excluded.url,
        method=excluded.method,
        params=excluded.params,
        response=excluded.response,
        updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
    '''
    data = [(r['id'], r['url'], r['method'], r['params'], r['response']) for r in records]
    with self._lock:
      conn = self._conn
      conn.execute('BEGIN TRANSACTION')
      try:
        conn.executemany(sql, data)
        conn.execute('COMMIT')
      except Exception:
        conn.execute('ROLLBACK')
        raise
      finally:
        self._wal_checkpoint_passive()

  # 查询 api 数据列表
  def get_api_list(self, type: str = None, reverse: bool = False) -> list:
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
  def update_api(self, record: dict) -> bool:
    with self._lock:
      conn = self._conn
      conn.execute('BEGIN TRANSACTION')
      try:
        # 1. 查询旧记录
        row = conn.execute(
          'SELECT type, url, method, params, response FROM api_data WHERE id=?',
          (record.get('id'),),
        ).fetchone()
        if row is None:
          conn.execute('ROLLBACK')
          return False

        # 2. 字段级合并：前端只传修改的字段时，旧值保留
        old = {
          'type': row[0],
          'url': row[1],
          'method': row[2],
          'params': row[3],
          'response': row[4],
        }
        merged = {
          'type': record.get('type') or old['type'],
          'url': record.get('url') or old['url'],
          'method': record.get('method') or old['method'],
          'params': record.get('params') or old['params'],
          'response': record.get('response') or old['response'],
        }

        # 3. 写入合并后的完整记录
        conn.execute(
          '''UPDATE api_data SET
               type=?, url=?, method=?, params=?, response=?,
               updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
             WHERE id=?''',
          (merged['type'], merged['url'], merged['method'],
           merged['params'], merged['response'], record.get('id')),
        )
        conn.execute('COMMIT')
        return True
      except Exception:
        conn.execute('ROLLBACK')
        raise

  # 按 id 删除 api 数据
  def delete_api(self, api_id: str) -> bool:
    with self._lock:
      conn = self._conn
      conn.execute('BEGIN TRANSACTION')
      try:
        cursor = conn.execute('DELETE FROM api_data WHERE id=?', (api_id,))
        if cursor.rowcount == 0:
          conn.execute('ROLLBACK')
          return False
        conn.execute('COMMIT')
        return True
      except Exception:
        conn.execute('ROLLBACK')
        raise

  # 批量写静态资源到 DB
  def batch_upsert_static(self, records: list) -> None:
    if not records:
      return
    sql = '''
      INSERT INTO static_data (url, type) VALUES (?, 'MITMPROXY')
      ON CONFLICT(url) DO UPDATE SET updated_at=strftime('%Y-%m-%d %H:%M:%f','now','localtime')
    '''
    data = [(url,) for url in records]
    with self._lock:
      conn = self._conn
      conn.execute('BEGIN TRANSACTION')
      try:
        conn.executemany(sql, data)
        conn.execute('COMMIT')
      except Exception:
        conn.execute('ROLLBACK')
        raise
      finally:
        self._wal_checkpoint_passive()

  # 查静态资源列表
  def get_static_list(self) -> list:
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
    with self._lock:
      if self._conn:
        self._conn.close()
        self._conn = None
