# -*- coding: utf-8 -*-
from app_types.db_types import ApiQuery, ApiRecord
from config.enum.BIZ_CODE import BIZ_SUCCESS


def _api(**kw) -> ApiRecord:
  base = ApiRecord(url='/api/x', method='GET', params='{}', response='{}', type='USER')
  base.update(kw)
  return base


def test_insert_returns_id_and_success(mock_db):
  r = mock_db.insert_api(_api())
  assert r['status_code'] == BIZ_SUCCESS
  assert r['id']


def test_insert_and_get_detail(mock_db):
  r = mock_db.insert_api(_api(url='/api/users', response='{"a": 1}'))
  d = mock_db.get_api_detail(r['id'])
  assert d['url'] == '/api/users'
  assert d['method'] == 'GET'
  assert d['enabled'] is True
  assert d['type'] == 'USER'
  assert d['response_variants'] == []


def test_insert_missing_url_fails(mock_db):
  assert mock_db.insert_api(_api(url=''))['status_code'] != BIZ_SUCCESS


def test_insert_invalid_method(mock_db):
  assert mock_db.insert_api(_api(method='PUT'))['status_code'] != BIZ_SUCCESS


def test_insert_get_forces_none_ct(mock_db):
  r = mock_db.insert_api(_api(method='GET', request_content_type='APPLICATION_JSON'))
  assert mock_db.get_api_detail(r['id'])['request_content_type'] == 'NONE'


def test_pagination(mock_db):
  for i in range(25):
    mock_db.insert_api(_api(url=f'/api/{i:02d}'))
  assert mock_db.get_api_count(ApiQuery()) == 25
  assert len(mock_db.get_api_list_page(ApiQuery(), page_num=1, page_size=10)) == 10
  assert len(mock_db.get_api_list_page(ApiQuery(), page_num=3, page_size=10)) == 5


def test_url_like_filter(mock_db):
  mock_db.insert_api(_api(url='/api/users'))
  mock_db.insert_api(_api(url='/api/orders'))
  assert mock_db.get_api_count(ApiQuery(url_like='users')) == 1


def test_method_filter(mock_db):
  mock_db.insert_api(_api(url='/a', method='GET'))
  mock_db.insert_api(_api(url='/b', method='POST', request_content_type='APPLICATION_JSON'))
  assert mock_db.get_api_count(ApiQuery(method='POST')) == 1


def test_api_types_filter(mock_db):
  mock_db.insert_api(_api(url='/a', type='USER'))
  mock_db.insert_api(_api(url='/b', type='MITMPROXY'))
  mock_db.insert_api(_api(url='/c', type='MCP'))
  mock_db.insert_api(_api(url='/d', type='TEST_GROUP'))
  rows = mock_db.get_api_list(ApiQuery(api_types=['USER', 'MCP']))
  assert {r['url'] for r in rows} == {'/a', '/c'}


def test_update_api(mock_db):
  r = mock_db.insert_api(_api())
  r2 = mock_db.update_api(ApiRecord(id=r['id'], url='/api/y', timeout=500))
  assert r2['status_code'] == BIZ_SUCCESS
  d = mock_db.get_api_detail(r['id'])
  assert d['url'] == '/api/y'
  assert d['timeout'] == 500


def test_delete_api(mock_db):
  r = mock_db.insert_api(_api())
  assert mock_db.delete_api(r['id'])['status_code'] == BIZ_SUCCESS
  assert mock_db.get_api_detail(r['id']) is None


def test_group_id_filter(mock_db):
  group_id = mock_db.insert_test_group({'name': 'g', 'operator': 'USER'})['id']
  mock_db.insert_api(_api(url='/in', type='TEST_GROUP', group_id=group_id))
  mock_db.insert_api(_api(url='/out', type='USER'))
  rows = mock_db.get_api_list(ApiQuery(group_id=group_id))
  assert {r['url'] for r in rows} == {'/in'}
  # 详情/列表行映射均带出 group_id 字段
  assert rows[0]['group_id'] == group_id
  assert mock_db.get_api_detail(rows[0]['id'])['group_id'] == group_id


def test_unfiltered_query_includes_test_group(mock_db):
  # DB 层无类型条件不做白名单兜底（兜底在 GUI/MCP 调用方），TEST_GROUP 行会返回——
  # 这就是常规查询必须显式兜 api_types=MOCK_API_TYPE_PRIORITY 的原因
  mock_db.insert_api(_api(url='/t', type='TEST_GROUP'))
  rows = mock_db.get_api_list(ApiQuery())
  assert any(r['type'] == 'TEST_GROUP' for r in rows)


def test_update_preserves_group_id(mock_db):
  # group_id 创建后不可变：update 传入也不生效（同 type 规制）
  group_id = mock_db.insert_test_group({'name': 'g', 'operator': 'USER'})['id']
  r = mock_db.insert_api(_api(type='TEST_GROUP', group_id=group_id))
  r2 = mock_db.update_api(ApiRecord(id=r['id'], url='/api/y', group_id='other'))
  assert r2['status_code'] == BIZ_SUCCESS
  d = mock_db.get_api_detail(r['id'])
  assert d['url'] == '/api/y'
  assert d['group_id'] == group_id


def test_v6_migration_from_v5(tmp_work_dir, tmp_path):
  # v5 存量库升级到 v6：api_data.group_id 列 + test_group 表补齐，存量数据保留
  import sqlite3
  from importlib.resources import read_text

  from lib.db import MockDBCache

  db_path = tmp_path / 'data' / 'mock.db'
  conn = sqlite3.connect(str(db_path))
  conn.executescript(read_text('schema', 'v5.sql'))
  conn.execute('INSERT INTO api_data (id, url) VALUES (?, ?)', ('a1', '/old'))
  conn.execute('PRAGMA user_version = 5')
  conn.commit()  # 默认非 autocommit，必须提交落盘才算「v5 存量库」
  conn.close()

  try:
    db = MockDBCache.get(tmp_work_dir)
    assert db._conn.execute('PRAGMA user_version').fetchone()[0] == 6
    cols = {r[1] for r in db._conn.execute('PRAGMA table_info(api_data)').fetchall()}
    assert 'group_id' in cols
    tables = {r[0] for r in db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert 'test_group' in tables
    row = db.get_api_detail('a1')
    assert row['url'] == '/old'
    assert row['group_id'] == ''
  finally:
    MockDBCache.close_all()


def test_v6_schema_fresh_db(tmp_work_dir):
  # 新库直接按 v6.sql 建表：group_id 列与 test_group 表随建表即有
  from lib.db import MockDBCache

  try:
    db = MockDBCache.get(tmp_work_dir)
    assert db._conn.execute('PRAGMA user_version').fetchone()[0] == 6
    cols = {r[1] for r in db._conn.execute('PRAGMA table_info(api_data)').fetchall()}
    assert 'group_id' in cols
    # 幂等：关闭后重开同一路径，重复迁移不应报错
    MockDBCache.close_all()
    db = MockDBCache.get(tmp_work_dir)
    assert db._conn.execute('PRAGMA user_version').fetchone()[0] == 6
  finally:
    MockDBCache.close_all()
