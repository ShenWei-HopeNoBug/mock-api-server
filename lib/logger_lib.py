# -*- coding: utf-8 -*-
import logging
import sys
from logging import INFO, Logger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_stream_logger_handler(log_level: int = INFO) -> Optional[logging.StreamHandler]:
  # PyInstaller -w 打包态下 sys.stderr 为 None，StreamHandler emit 会抛 AttributeError，
  # 该环境下不挂控制台 handler，仅保留文件日志
  if sys.stderr is None:
    return None
  handler = logging.StreamHandler()
  handler.setLevel(log_level)
  formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
  handler.setFormatter(formatter)
  return handler


def get_file_logger_handler(log_level: int = INFO) -> RotatingFileHandler:
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

  formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

  handler.setFormatter(formatter)
  return handler


# 日志处理器（stream 在无控制台环境下为 None，setup_logger 会跳过挂载）
STREAM_LOGGER_HANDLER: Optional[logging.StreamHandler] = get_stream_logger_handler()
FILE_LOGGER_HANDLER = get_file_logger_handler()


def setup_logger(logger_name: str = 'logger', log_level: int = INFO) -> Logger:
  logger = logging.getLogger(logger_name)
  logger.setLevel(log_level)
  # 如果已经配置过处理器，直接返回
  if logger.handlers:
    return logger

  if STREAM_LOGGER_HANDLER is not None:
    logger.addHandler(STREAM_LOGGER_HANDLER)
  logger.addHandler(FILE_LOGGER_HANDLER)
  return logger


# 分域全局日志：全部共用同一组 handler，统一写入 logs/app.log 与控制台，
# 通过 logger 名（%(name)s）在日志中区分来源模块
APP_LOGGER: Logger = setup_logger(logger_name='APP')
MOCK_LOGGER: Logger = setup_logger(logger_name='MOCK')
STATIC_LOGGER: Logger = setup_logger(logger_name='STATIC')
CATCH_LOGGER: Logger = setup_logger(logger_name='CATCH')
MCP_LOGGER: Logger = setup_logger(logger_name='MCP')
APPSRV_LOGGER: Logger = setup_logger(logger_name='APPSRV')
DB_LOGGER: Logger = setup_logger(logger_name='DB')
DOWNLOAD_LOGGER: Logger = setup_logger(logger_name='DOWNLOAD')
