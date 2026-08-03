# -*- coding: utf-8 -*-
import contextlib
import threading
import sqlite3
from importlib.resources import read_text

from lib.logger_lib import APP_LOGGER
from .utils import _ensure_open


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
