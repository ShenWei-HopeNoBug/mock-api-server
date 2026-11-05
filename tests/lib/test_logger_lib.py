# -*- coding: utf-8 -*-
import logging
import queue
import time
from logging.handlers import QueueHandler, RotatingFileHandler

import pytest

import lib.logger_lib as ll


def _handlers_of(logger, htype):
  # pytest caplog 插件会往 logger 里挂 LogCaptureHandler；
  # 精确类型匹配（不用 isinstance），避免 StreamHandler 子类互相误计
  return [h for h in logger.handlers if type(h) is htype]


@pytest.fixture(autouse=True)
def _reset_logging(tmp_path, monkeypatch):
  """复位 logger_lib 模块全局态 + 剥离域 logger 已挂 handler；
  chdir 到 tmp，parent 模式建的 logs/app.log 不污染仓库"""
  monkeypatch.chdir(tmp_path)
  monkeypatch.setattr(ll, '_LOG_CONFIGURED', False)
  monkeypatch.setattr(ll, '_LOG_QUEUE', None)
  monkeypatch.setattr(ll, '_LOG_LISTENER', None)
  for lg in ll._DOMAIN_LOGGERS:
    for h in list(lg.handlers):
      lg.removeHandler(h)
  yield
  ll.shutdown_logging()
  for lg in ll._DOMAIN_LOGGERS:
    for h in list(lg.handlers):
      lg.removeHandler(h)


def test_child_attaches_queue_handler():
  ll.configure_logging('child', queue.Queue())
  for lg in ll._DOMAIN_LOGGERS:
    assert len(_handlers_of(lg, QueueHandler)) == 1


def test_child_record_arrives_via_queue():
  q = queue.Queue()
  ll.configure_logging('child', q)
  ll.APP_LOGGER.info('hello-child')
  rec = q.get(timeout=2)
  assert rec.name == 'APP'
  assert 'hello-child' in rec.getMessage()


def test_child_none_queue_raises():
  with pytest.raises(ValueError):
    ll.configure_logging('child', None)


def test_unknown_role_raises():
  with pytest.raises(ValueError):
    ll.configure_logging('alien')


def test_invalid_call_does_not_poison_config():
  """非法 configure 调用不应置位 _LOG_CONFIGURED，否则后续正确配置被静默跳过"""
  with pytest.raises(ValueError):
    ll.configure_logging('alien')
  with pytest.raises(ValueError):
    ll.configure_logging('child', None)
  ll.configure_logging('child', queue.Queue())   # 不应被前两次失败置位拦截
  assert len(_handlers_of(ll.APP_LOGGER, QueueHandler)) == 1


def test_configure_idempotent():
  q = queue.Queue()
  ll.configure_logging('child', q)
  ll.configure_logging('child', q)   # 已配置直接返回，不重复挂 handler
  assert len(_handlers_of(ll.APP_LOGGER, QueueHandler)) == 1


def test_get_log_queue_requires_parent():
  with pytest.raises(RuntimeError):
    ll.get_log_queue()


def test_parent_writes_file_and_consumes_queue(tmp_path):
  ll.configure_logging('parent')
  assert len(_handlers_of(ll.APP_LOGGER, RotatingFileHandler)) == 1   # FILE + STREAM
  assert len(_handlers_of(ll.APP_LOGGER, logging.StreamHandler)) == 1
  # 模拟子进程投递：手工构造 LogRecord 入队
  ll.get_log_queue().put(logging.LogRecord('CATCH', logging.INFO, __file__, 1, 'child-record', None, None))
  ll.APP_LOGGER.info('parent-record')
  log_file = tmp_path / 'logs' / 'app.log'
  deadline = time.time() + 3
  content = ''
  while time.time() < deadline:
    if log_file.exists():
      content = log_file.read_text(encoding='utf-8')
      if 'child-record' in content:
        break
    time.sleep(0.05)
  assert 'child-record' in content
  assert 'CATCH' in content
  assert 'parent-record' in content


def test_shutdown_logging_idempotent():
  ll.shutdown_logging()   # 未配置时调用不报错
  ll.shutdown_logging()
