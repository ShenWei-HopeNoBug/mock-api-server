# -*- coding: utf-8 -*-
import logging
from logging import Logger, INFO
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_stream_logger_handler(log_level: int = INFO) -> logging.StreamHandler:
  handler = logging.StreamHandler()
  handler.setLevel(log_level)
  formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
  )
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

  formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
  )

  handler.setFormatter(formatter)
  return handler


# 日志处理器
STREAM_LOGGER_HANDLER = get_stream_logger_handler()
FILE_LOGGER_HANDLER = get_file_logger_handler()


def setup_logger(logger_name: str = 'logger', log_level: int = INFO) -> Logger:
  logger = logging.getLogger(logger_name)
  logger.setLevel(log_level)
  # 如果已经配置过处理器，直接返回
  if logger.handlers:
    return logger

  logger.addHandler(STREAM_LOGGER_HANDLER)
  logger.addHandler(FILE_LOGGER_HANDLER)
  return logger


# 主进程全局日志
APP_LOGGER: Logger = setup_logger(logger_name='APP')
