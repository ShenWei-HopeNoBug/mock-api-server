# -*- coding: utf-8 -*-
import logging


def get_stream_logger_handler():
  handler = logging.StreamHandler()
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
  handler.setFormatter(formatter)
  return handler


# 日志处理器
STREAM_LOGGER_HANDLER = get_stream_logger_handler()


def setup_stream_logger(logger_name='logger'):
  logger = logging.getLogger(logger_name)
  logger.setLevel(logging.INFO)
  logger.addHandler(STREAM_LOGGER_HANDLER)
  return logger


# 主进程全局日志
APP_LOGGER = setup_stream_logger('APP')
