# -*- coding: utf-8 -*-
import pytest
from flask import Flask

from lib.db import MockDBCache
from lib.server_lib import MockRequestHandler, ThreadSafeLRUCache
from lib.utils_lib import create_md5


@pytest.fixture()
def tmp_work_dir(tmp_path):
  """构造最小 work_dir（含 data/config 目录），供 MockDB/文件类测试使用"""
  (tmp_path / 'data').mkdir()
  (tmp_path / 'config').mkdir()
  return str(tmp_path)


@pytest.fixture()
def mock_db(tmp_work_dir):
  """tmp work_dir 下的 MockDB；teardown 必须清掉类级 _cache 避免测试间串库"""
  db = MockDBCache.get(tmp_work_dir)
  yield db
  MockDBCache.close_all()


@pytest.fixture()
def flask_app():
  """独立 Flask 实例，供 request context / test_client 用例使用"""
  app = Flask('test')
  app.config['TESTING'] = True
  return app


def make_request_key(route: str, method: str, request_content_type: str) -> str:
  """与 module.mock_server.__get_request_dict_key 同实现"""
  return create_md5(f'{route}-{method}-{request_content_type}')


def make_response_key(method: str, request_content_type: str, params: str) -> str:
  """与 module.mock_server.__get_response_dict_key 同实现"""
  return create_md5(f'{method}-{request_content_type}-{params}')


@pytest.fixture()
def make_handler(tmp_work_dir):
  """MockRequestHandler 工厂：注入 dict/lambda，key 函数与 MockServer 真实实现一致"""
  def _make(mock_api_map=None, response_delay: int = 0) -> MockRequestHandler:
    return MockRequestHandler(
      mock_api_map=mock_api_map or {},
      work_dir=tmp_work_dir,
      response_cache=ThreadSafeLRUCache(limit=16),
      response_delay=response_delay,
      get_request_key=make_request_key,
      get_response_key=make_response_key,
    )
  return _make
