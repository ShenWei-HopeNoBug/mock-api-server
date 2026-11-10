# -*- coding: utf-8 -*-
from app_types.db_types import ApiRecord
from config.enum import SERVER
from lib.app_lib import get_mock_api_data_list


def _api(**kw) -> ApiRecord:
  base = ApiRecord(url='/api/x', method='GET', params='{}', response='{}', type='USER')
  base.update(kw)
  return base


def test_mock_api_data_list_type_priority_order(mock_db, tmp_work_dir):
  # 乱序插入三种类型，返回应按 MOCK_API_TYPE_PRIORITY 分段；白名单外类型不参与
  mock_db.insert_api(_api(url='/u1', type='USER'))
  mock_db.insert_api(_api(url='/m1', type='MITMPROXY'))
  mock_db.insert_api(_api(url='/c1', type='MCP'))
  mock_db.insert_api(_api(url='/u2', type='USER'))
  mock_db.insert_api(_api(url='/t1', type='TEST_GROUP'))

  rows = get_mock_api_data_list(work_dir=tmp_work_dir)
  types = [r['type'] for r in rows]
  assert 'TEST_GROUP' not in types
  assert types == sorted(types, key=SERVER.MOCK_API_TYPE_PRIORITY.index)
  assert types.count('USER') == 2


def test_mock_api_data_list_enabled_filter(mock_db, tmp_work_dir):
  mock_db.insert_api(_api(url='/on', enabled=True))
  mock_db.insert_api(_api(url='/off', enabled=False))

  urls_all = {r['url'] for r in get_mock_api_data_list(work_dir=tmp_work_dir)}
  assert urls_all == {'/on', '/off'}

  urls_enabled = {r['url'] for r in get_mock_api_data_list(work_dir=tmp_work_dir, enabled=True)}
  assert urls_enabled == {'/on'}
