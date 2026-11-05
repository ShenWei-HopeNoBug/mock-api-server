# -*- coding: utf-8 -*-
from app_types.db_types import ApiResponseVariantInsertRecord, ApiResponseVariantRecord
from config.enum.BIZ_CODE import BIZ_DATA_NOT_FOUND, BIZ_SUCCESS


def _api_id(mock_db) -> str:
  return mock_db.insert_api({'url': '/api/x', 'method': 'GET', 'params': '{}', 'response': '{}'})['id']


def _variant(api_id: str, **kw) -> ApiResponseVariantInsertRecord:
  base = ApiResponseVariantInsertRecord(api_data_id=api_id, name='v1', response='{"v": 1}')
  base.update(kw)
  return base


def test_insert_and_get_by_id(mock_db):
  aid = _api_id(mock_db)
  r = mock_db.insert_variant(_variant(aid))
  assert r['status_code'] == BIZ_SUCCESS
  assert r['id']
  v = mock_db.get_variant_by_id(r['id'])
  assert v['name'] == 'v1'
  assert v['api_data_id'] == aid


def test_insert_orphan_variant_fails(mock_db):
  r = mock_db.insert_variant(_variant('nonexistent-api'))
  assert r['status_code'] == BIZ_DATA_NOT_FOUND


def test_variants_by_api_id_ordered(mock_db):
  aid = _api_id(mock_db)
  mock_db.insert_variant(_variant(aid, name='v1'))
  mock_db.insert_variant(_variant(aid, name='v2'))
  names = [v['name'] for v in mock_db.get_variants_by_api_id(aid)]
  assert names == ['v1', 'v2']   # 按 response_variant_ids 插入序返回


def test_detail_includes_variants(mock_db):
  aid = _api_id(mock_db)
  mock_db.insert_variant(_variant(aid))
  d = mock_db.get_api_detail(aid)
  assert len(d['response_variants']) == 1
  assert d['response_variants'][0]['name'] == 'v1'


def test_update_variant(mock_db):
  aid = _api_id(mock_db)
  vid = mock_db.insert_variant(_variant(aid))['id']
  r = mock_db.update_variant(ApiResponseVariantRecord(id=vid, name='v-renamed'))
  assert r['status_code'] == BIZ_SUCCESS
  assert mock_db.get_variant_by_id(vid)['name'] == 'v-renamed'


def test_delete_variant_syncs_id_list(mock_db):
  aid = _api_id(mock_db)
  vid = mock_db.insert_variant(_variant(aid))['id']
  assert mock_db.delete_variant(vid)['status_code'] == BIZ_SUCCESS
  assert mock_db.get_variant_by_id(vid) is None
  # 同步从 api_data.response_variant_ids 移除
  assert mock_db.get_api_detail(aid)['response_variants'] == []
