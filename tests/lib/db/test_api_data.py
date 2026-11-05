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
