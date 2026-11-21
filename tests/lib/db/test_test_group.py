# -*- coding: utf-8 -*-
from app_types.db_types import ApiRecord
from app_types.db_types import TestGroupRecord as GroupRecord  # 别名避开 pytest 按 Test* 收集
from config.enum.BIZ_CODE import BIZ_SUCCESS


def _api(**kw) -> ApiRecord:
  base = ApiRecord(url='/api/x', method='GET', params='{}', response='{}', type='USER')
  base.update(kw)
  return base


def _group(**kw) -> GroupRecord:
  base = GroupRecord(name='g', operator='USER')
  base.update(kw)
  return base


def _make_group_with_item(mock_db, api_kw=None, enabled=True):
  """建组并把一条新 api 拷入组，返回 (group_id, src_api_id, item_id)"""
  group_id = mock_db.insert_test_group(_group())['id']
  api_id = mock_db.insert_api(_api(**(api_kw or {})))['id']
  item_id = mock_db.copy_api_to_group(api_id, group_id, enabled=enabled, operator='USER')['id']
  return group_id, api_id, item_id


def test_insert_group_defaults_disabled(mock_db):
  r = mock_db.insert_test_group(_group(name='回归组'))
  assert r['status_code'] == BIZ_SUCCESS
  assert r['id']
  g = mock_db.get_test_group(r['id'])
  assert g['name'] == '回归组'
  assert g['enabled'] is False
  assert g['operator'] == 'USER'
  assert g['items'] == []


def test_update_group_name_only(mock_db):
  group_id = mock_db.insert_test_group(_group(name='old'))['id']
  mock_db.enable_test_group(group_id)
  r = mock_db.update_test_group(GroupRecord(id=group_id, name='new', operator='MCP'))
  assert r['status_code'] == BIZ_SUCCESS
  g = mock_db.get_test_group(group_id)
  assert g['name'] == 'new'
  assert g['operator'] == 'MCP'
  # enabled 不经 update 修改，保持启用态
  assert g['enabled'] is True


def test_update_missing_group_fails(mock_db):
  assert mock_db.update_test_group(GroupRecord(id='nope', name='x'))['status_code'] != BIZ_SUCCESS


def test_delete_group_cascade(mock_db):
  group_id, api_id, item_id = _make_group_with_item(mock_db)
  mock_db.insert_variant({'api_data_id': item_id, 'name': 'v1', 'response': '{}'})
  r = mock_db.delete_test_group(group_id)
  assert r['status_code'] == BIZ_SUCCESS
  # 组行/组内副本/副本变体级联删除，源 api 数据不受影响
  assert mock_db.get_test_group(group_id) is None
  assert mock_db.get_api_detail(item_id) is None
  assert mock_db.get_variants_by_api_id(item_id) == []
  assert mock_db.get_api_detail(api_id) is not None


def test_delete_missing_group_fails(mock_db):
  assert mock_db.delete_test_group('nope')['status_code'] != BIZ_SUCCESS


def test_group_list_item_count(mock_db):
  group_id, _, _ = _make_group_with_item(mock_db)
  empty_id = mock_db.insert_test_group(_group(name='empty'))['id']
  by_id = {r['id']: r for r in mock_db.get_test_group_list()}
  assert by_id[group_id]['item_count'] == 1
  assert by_id[empty_id]['item_count'] == 0


def test_enable_atomic_replacement(mock_db):
  g1 = mock_db.insert_test_group(_group(name='g1'))['id']
  g2 = mock_db.insert_test_group(_group(name='g2'))['id']
  mock_db.enable_test_group(g1)
  assert mock_db.get_enabled_test_group_id() == g1
  mock_db.enable_test_group(g2)
  # 原子顶替：全局至多一行 enabled=1
  assert mock_db.get_enabled_test_group_id() == g2
  assert mock_db.get_test_group(g1)['enabled'] is False
  assert sum(1 for r in mock_db.get_test_group_list() if r['enabled']) == 1


def test_enable_missing_group_keeps_state(mock_db):
  group_id = mock_db.insert_test_group(_group())['id']
  mock_db.enable_test_group(group_id)
  assert mock_db.enable_test_group('nope')['status_code'] != BIZ_SUCCESS
  assert mock_db.get_enabled_test_group_id() == group_id


def test_disable_clears_all(mock_db):
  group_id = mock_db.insert_test_group(_group())['id']
  mock_db.enable_test_group(group_id)
  r = mock_db.disable_test_group()
  assert r['status_code'] == BIZ_SUCCESS
  assert mock_db.get_enabled_test_group_id() is None
  assert mock_db.get_test_group(group_id)['enabled'] is False


def test_get_enabled_test_group_id_empty(mock_db):
  assert mock_db.get_enabled_test_group_id() is None


def test_copy_api_to_group_with_variants(mock_db):
  api_id = mock_db.insert_api(_api(
    url='/api/order', method='POST',
    request_content_type='APPLICATION_JSON', response='{"ok":1}',
  ))['id']
  mock_db.insert_variant({'api_data_id': api_id, 'name': 'v1', 'response': '{"ok":1}', 'enabled': True})
  mock_db.insert_variant({'api_data_id': api_id, 'name': 'v2', 'response': '{"ok":2}', 'enabled': False})
  group_id = mock_db.insert_test_group(_group())['id']

  r = mock_db.copy_api_to_group(api_id, group_id, copy_variants=True, enabled=True, operator='USER')
  assert r['status_code'] == BIZ_SUCCESS
  item = mock_db.get_api_detail(r['id'])
  assert item['type'] == 'TEST_GROUP'
  assert item['group_id'] == group_id
  assert item['enabled'] is True
  assert item['url'] == '/api/order'
  assert item['method'] == 'POST'
  assert item['request_content_type'] == 'APPLICATION_JSON'
  # 变体按源顺序拷贝：保留 name 与 enabled 态，绑定列表重建为新 id
  copied = item['response_variants']
  assert [v['name'] for v in copied] == ['v1', 'v2']
  assert [v['enabled'] for v in copied] == [True, False]
  assert [v['type'] for v in copied] == ['USER', 'USER']
  assert item['response_variant_ids'] == [v['id'] for v in copied]
  # 源 api 数据不受影响
  src = mock_db.get_api_detail(api_id)
  assert src['type'] == 'USER'
  assert src['group_id'] == ''
  assert len(src['response_variants']) == 2


def test_copy_api_to_group_without_variants(mock_db):
  api_id = mock_db.insert_api(_api())['id']
  mock_db.insert_variant({'api_data_id': api_id, 'name': 'v1'})
  group_id = mock_db.insert_test_group(_group())['id']
  r = mock_db.copy_api_to_group(api_id, group_id, copy_variants=False)
  assert r['status_code'] == BIZ_SUCCESS
  item = mock_db.get_api_detail(r['id'])
  assert item['response_variant_ids'] == []
  assert item['response_variants'] == []


def test_copy_api_to_group_disabled(mock_db):
  api_id = mock_db.insert_api(_api())['id']
  group_id = mock_db.insert_test_group(_group())['id']
  r = mock_db.copy_api_to_group(api_id, group_id, enabled=False)
  assert r['status_code'] == BIZ_SUCCESS
  assert mock_db.get_api_detail(r['id'])['enabled'] is False


def test_copy_api_to_group_default_enabled(mock_db):
  api_id = mock_db.insert_api(_api())['id']
  group_id = mock_db.insert_test_group(_group())['id']
  r = mock_db.copy_api_to_group(api_id, group_id)
  assert mock_db.get_api_detail(r['id'])['enabled'] is True


def test_copy_to_missing_group_fails(mock_db):
  api_id = mock_db.insert_api(_api())['id']
  r = mock_db.copy_api_to_group(api_id, 'nope')
  assert r['status_code'] != BIZ_SUCCESS
  assert r['id'] is None


def test_copy_missing_api_fails(mock_db):
  group_id = mock_db.insert_test_group(_group())['id']
  r = mock_db.copy_api_to_group('nope', group_id)
  assert r['status_code'] != BIZ_SUCCESS
  assert r['id'] is None
