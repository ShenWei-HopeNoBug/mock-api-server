# -*- coding: utf-8 -*-
import logging
import multiprocessing
import sys
from logging import INFO, Logger
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from multiprocessing.queues import Queue
from pathlib import Path
from typing import List, Optional

LOG_FORMAT = '%(asctime)s - %(processName)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 父进程侧日志基建状态：mp.Queue 在 configure_logging('parent') 时创建，
# QueueListener 线程消费子进程 LogRecord 并复用同一组文件/控制台 handler 落盘
_LOG_QUEUE: Optional[Queue] = None
_LOG_LISTENER: Optional[QueueListener] = None
_LOG_CONFIGURED: bool = False


def _get_stream_handler(log_level: int = INFO) -> Optional[logging.StreamHandler]:
  # PyInstaller -w 打包态下 sys.stderr 为 None，StreamHandler emit 会抛 AttributeError，
  # 该环境下不挂控制台 handler，仅保留文件日志
  if sys.stderr is None:
    return None
  handler = logging.StreamHandler()
  handler.setLevel(log_level)
  handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
  return handler


def _get_file_handler(log_level: int = INFO) -> RotatingFileHandler:
  # 创建日志目录（如果不存在）
  log_dir = Path('logs')
  log_dir.mkdir(exist_ok=True)

  # 创建文件处理器，限制单个日志文件最大10MB，最多保留5个备份
  log_file = log_dir / 'app.log'
  handler = RotatingFileHandler(
    log_file,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
  )
  handler.setLevel(log_level)
  handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
  return handler


def setup_logger(logger_name: str = 'logger', log_level: int = INFO) -> Logger:
  # 仅创建 logger 本体；handler 由 configure_logging 按进程角色统一挂载。
  # 子进程 import 本模块不再打开日志文件句柄——多进程共写轮转 rename 冲突的根因
  logger = logging.getLogger(logger_name)
  logger.setLevel(log_level)
  logger.propagate = False
  return logger


# 分域全局日志：handler 由 configure_logging 统一挂载，
# 通过 logger 名（%(name)s）与进程名（%(processName)s）在日志中区分来源
APP_LOGGER: Logger = setup_logger(logger_name='APP')
MOCK_LOGGER: Logger = setup_logger(logger_name='MOCK')
STATIC_LOGGER: Logger = setup_logger(logger_name='STATIC')
CATCH_LOGGER: Logger = setup_logger(logger_name='CATCH')
MCP_LOGGER: Logger = setup_logger(logger_name='MCP')
APPSRV_LOGGER: Logger = setup_logger(logger_name='APPSRV')
DB_LOGGER: Logger = setup_logger(logger_name='DB')
DOWNLOAD_LOGGER: Logger = setup_logger(logger_name='DOWNLOAD')

_DOMAIN_LOGGERS: List[Logger] = [
  APP_LOGGER, MOCK_LOGGER, STATIC_LOGGER, CATCH_LOGGER,
  MCP_LOGGER, APPSRV_LOGGER, DB_LOGGER, DOWNLOAD_LOGGER,
]


def configure_logging(role: str, queue: Optional[Queue] = None, log_level: int = INFO) -> None:
  """按进程角色挂载日志 handler：
  - parent：GUI 主进程。独占文件/控制台 handler，建 mp.Queue 并起 QueueListener 汇聚子进程记录；
  - child ：服务子进程。仅挂 QueueHandler，把 LogRecord 经 mp.Queue 交给父进程统一落盘。
  """
  global _LOG_QUEUE, _LOG_LISTENER, _LOG_CONFIGURED
  if _LOG_CONFIGURED:
    return
  _LOG_CONFIGURED = True

  if role == 'child':
    if queue is None:
      raise ValueError('child 角色必须传入父进程创建的 mp.Queue')
    queue_handler = QueueHandler(queue)
    for logger in _DOMAIN_LOGGERS:
      logger.addHandler(queue_handler)
    return

  if role != 'parent':
    raise ValueError(f'未知日志进程角色: {role}')

  _LOG_QUEUE = multiprocessing.Queue()
  sink_handlers: List[logging.Handler] = [
    h for h in (_get_file_handler(log_level), _get_stream_handler(log_level)) if h is not None
  ]
  for logger in _DOMAIN_LOGGERS:
    for handler in sink_handlers:
      logger.addHandler(handler)
  _LOG_LISTENER = QueueListener(_LOG_QUEUE, *sink_handlers, respect_handler_level=True)
  _LOG_LISTENER.start()


def get_log_queue() -> Queue:
  """取父进程日志队列供子进程 spawn 传参；须在 configure_logging('parent') 之后调用"""
  if _LOG_QUEUE is None:
    raise RuntimeError("get_log_queue 须在 configure_logging('parent') 之后调用")
  return _LOG_QUEUE


def shutdown_logging() -> None:
  """停止 QueueListener，排空已入队的子进程日志记录"""
  global _LOG_LISTENER
  if _LOG_LISTENER is not None:
    _LOG_LISTENER.stop()
    _LOG_LISTENER = None
