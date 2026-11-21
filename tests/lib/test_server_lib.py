# -*- coding: utf-8 -*-
import io
import json
import time

from flask import request

from config.route import SYSTEM_ROUTE
from lib.logger_lib import MOCK_LOGGER
from lib.server_lib import (
  ClientStateManager,
  parse_flask_request,
  register_system_routes,
)
from lib.utils_lib import JsonFormat, create_md5


def _params_json(params):
  """与 MockServer.__get_params_json_string 同实现"""
  if isinstance(params, dict):
    return JsonFormat.sort_dumps(params)
  if isinstance(params, str):
    return JsonFormat.format_and_sort_json_string(params)
  return '{}'


def _variants(*timeouts):
  return [{'id': f'v{i}', 'timeout': t} for i, t in enumerate(timeouts, start=1)]


def _meta(**kw):
  base = {'api_data_id': 'a1', 'timeout': 0, 'variants': []}
  base.update(kw)
  return base


# ---------- _select_variant ----------


def test_select_variant_first_hit(make_handler):
  handler = make_handler()
  state = {}
  assert handler._select_variant(state, 'api1', _variants(0, 0)) == 'v1'
  assert state['variant_state']['api1']['next_index'] == 1


def test_select_variant_advance_and_stick(make_handler):
  handler = make_handler()
  state = {}
  vs = _variants(0, 0)
  assert handler._select_variant(state, 'api1', vs) == 'v1'
  assert handler._select_variant(state, 'api1', vs) == 'v2'
  assert handler._select_variant(state, 'api1', vs) == 'v2'  # 末位驻留


def test_select_variant_timeout_reset(make_handler, monkeypatch):
  handler = make_handler()
  vs = [{'id': 'v1', 'timeout': 1000}, {'id': 'v2', 'timeout': 1000}]
  clock = [1000.0]
  monkeypatch.setattr(time, 'time', lambda: clock[0])
  state = {}
  assert handler._select_variant(state, 'api1', vs) == 'v1'   # last_variant_timeout=1000ms
  clock[0] += 2.0      # idle 2000ms > 1000ms → 重置回首变体
  assert handler._select_variant(state, 'api1', vs) == 'v1'
  clock[0] += 0.5      # idle 500ms < 1000ms → 正常推进
  assert handler._select_variant(state, 'api1', vs) == 'v2'


def test_select_variant_zero_timeout_no_reset(make_handler, monkeypatch):
  handler = make_handler()
  vs = _variants(0, 0)
  clock = [1000.0]
  monkeypatch.setattr(time, 'time', lambda: clock[0])
  state = {}
  assert handler._select_variant(state, 'api1', vs) == 'v1'
  clock[0] += 3600     # timeout=0 不参与 idle 回退，间隔再久也继续推进
  assert handler._select_variant(state, 'api1', vs) == 'v2'


# ---------- _get_api_match_meta ----------


def test_meta_request_key_miss(make_handler):
  handler = make_handler()
  assert handler._get_api_match_meta('rk', 'rk2') is None


def test_meta_exact_hit(make_handler):
  handler = make_handler()
  meta = _meta()
  handler.mock_api_map = {'rk': {'rk2': meta}}
  assert handler._get_api_match_meta('rk', 'rk2') is meta


def test_meta_fallback_last_inserted(make_handler):
  handler = make_handler()
  m1, m2 = _meta(api_data_id='a1'), _meta(api_data_id='a2')
  handler.mock_api_map = {'rk': {'r1': m1, 'r2': m2}}
  assert handler._get_api_match_meta('rk', 'nope') is m2


def test_meta_empty_inner_none(make_handler):
  handler = make_handler()
  handler.mock_api_map = {'rk': {}}
  assert handler._get_api_match_meta('rk', 'rk2') is None


# ---------- _resolve_meta / 测试组遮蔽 ----------
#
# 「启动即冻结」语义：handler.group_api_map 是启动时装载的启用组快照（Optional[MockApiMap]），
# 进程生命周期内不变；组解析路径对 DB 零访问，启用态标志的运行时变更不影响已注入快照。


def test_group_exact_hit_masks_base(make_handler):
  """同 (request_key, response_key)：组快照精确命中 → 遮蔽 base"""
  handler = make_handler()
  rk = handler.get_request_key('/api/x', 'GET', 'NONE')
  resk = handler.get_response_key('GET', 'NONE', '{}')
  base_meta, group_meta = _meta(api_data_id='base1'), _meta(api_data_id='g_api')
  handler.mock_api_map = {rk: {resk: base_meta}}
  handler.group_api_map = {rk: {resk: group_meta}}
  assert handler._resolve_meta(rk, resk) is group_meta


def test_group_miss_falls_back_to_base(make_handler):
  """组快照有 request_key 但 response_key miss 且 base 有同 request_key → 落回 base 正常解析"""
  handler = make_handler()
  rk = handler.get_request_key('/api/x', 'GET', 'NONE')
  resk = handler.get_response_key('GET', 'NONE', '{}')
  base_meta, group_meta = _meta(api_data_id='base1'), _meta(api_data_id='g_api')
  handler.mock_api_map = {rk: {resk: base_meta}}
  handler.group_api_map = {rk: {'other_key': group_meta}}
  assert handler._resolve_meta(rk, resk) is base_meta


def test_group_only_api_last_entry_fallback(make_handler):
  """组独有接口（base 无同 request_key）且 response_key miss → 组内末位 fallback"""
  handler = make_handler()
  rk = handler.get_request_key('/api/only', 'GET', 'NONE')
  m1, m2 = _meta(api_data_id='g1'), _meta(api_data_id='g2')
  handler.group_api_map = {rk: {'r1': m1, 'r2': m2}}
  assert handler._resolve_meta(rk, 'nope') is m2


def test_base_fallback_unchanged_when_group_lacks_key(make_handler):
  """组快照不含该 request_key → base 既有「精确 → 末位」规则不变"""
  handler = make_handler()
  rk = handler.get_request_key('/api/x', 'GET', 'NONE')
  m1, m2 = _meta(api_data_id='b1'), _meta(api_data_id='b2')
  handler.mock_api_map = {rk: {'r1': m1, 'r2': m2}}
  # 组快照存在但不含目标 request_key，不参与解析
  handler.group_api_map = {'rk_other': {'r1': _meta(api_data_id='unused')}}
  assert handler._resolve_meta(rk, 'nope') is m2


def test_no_group_snapshot_uses_base(make_handler):
  """组快照为 None（启动时无启用组）→ 纯 base 解析"""
  handler = make_handler()
  rk = handler.get_request_key('/api/x', 'GET', 'NONE')
  resk = handler.get_response_key('GET', 'NONE', '{}')
  base_meta = _meta(api_data_id='base1')
  handler.mock_api_map = {rk: {resk: base_meta}}
  assert handler._resolve_meta(rk, resk) is base_meta


def test_group_path_never_touches_db(make_handler, monkeypatch):
  """组解析路径零 DB 访问：无论有无快照，_resolve_meta 均不触发 DB 查询"""
  from lib.db import MockDBCache

  def _boom(cls, work_dir='.'):
    raise AssertionError('不应发生 DB 查询')

  monkeypatch.setattr(MockDBCache, 'get', classmethod(_boom))
  handler = make_handler()
  meta = _meta()
  handler.mock_api_map = {'rk': {'resk': meta}}
  handler.group_api_map = {'rk_g': {'resk': _meta(api_data_id='g_api')}}
  assert handler._resolve_meta('rk', 'resk') is meta          # base 命中
  assert handler._resolve_meta('rk_g', 'resk') is not None    # 组快照命中


def test_group_snapshot_frozen_against_db_flags(make_handler, mock_db):
  """启动即冻结：启用态 DB 标志的运行时变更（启用/顶替/停用）不影响已注入快照的解析"""
  g1 = mock_db.insert_test_group({'name': 'g1', 'operator': 'USER'})['id']
  g2 = mock_db.insert_test_group({'name': 'g2', 'operator': 'USER'})['id']
  handler = make_handler()
  rk = handler.get_request_key('/api/x', 'GET', 'NONE')
  resk = handler.get_response_key('GET', 'NONE', '{}')
  m = _meta(api_data_id='g1_api')
  handler.group_api_map = {rk: {resk: m}}

  mock_db.enable_test_group(g1)
  assert handler._resolve_meta(rk, resk) is m   # 快照生效
  mock_db.enable_test_group(g2)                  # DB 层顶替到未装载组
  assert handler._resolve_meta(rk, resk) is m   # 仍按快照解析（冻结，遮蔽效果等重启）
  mock_db.disable_test_group()
  assert handler._resolve_meta(rk, resk) is m   # 停用也不影响快照（冻结）


def test_group_masked_404_via_handle(make_handler, flask_app):
  """组快照存在与否不改变「request_key 全缺失 → 404」语义"""
  handler = make_handler()
  handler.group_api_map = {'rk': {'resk': _meta()}}
  with flask_app.test_request_context():
    resp, status = handler.handle('GET', '/nope', 'NONE', '{}')
    assert status == 404
    assert resp.get_json() == {'error': 'No valid mock data'}


# ---------- ClientStateManager ----------


def test_csm_get_or_create():
  mgr = ClientStateManager(limit=10)
  r1 = mgr.get_or_create('dev1')
  assert r1['is_new'] is True
  r1['state']['x'] = 1
  r2 = mgr.get_or_create('dev1')
  assert r2['is_new'] is False
  assert r2['state']['x'] == 1


def test_csm_lru_eviction():
  mgr = ClientStateManager(limit=2)
  mgr.get_or_create('d1')
  mgr.get_or_create('d2')
  mgr.get_or_create('d1')   # d1 刷新为最近使用
  mgr.get_or_create('d3')   # 超上限 → 淘汰最久未用的 d2
  assert mgr.get('d2') is None
  assert mgr.get('d1') is not None
  assert mgr.get('d3') is not None


def test_csm_set_get_delete():
  mgr = ClientStateManager(limit=10)
  mgr.set('d1', {'k': 1})
  assert mgr.get('d1') == {'k': 1}
  mgr.delete('d1')
  assert mgr.get('d1') is None


# ---------- parse_flask_request ----------


def test_parse_get(flask_app):
  with flask_app.test_request_context('/api/users?a=1&b=2', method='GET'):
    parsed = parse_flask_request(request, 'api/users', _params_json)
    assert parsed.method == 'GET'
    assert parsed.route == '/api/users'        # GET 路由剥 query
    assert parsed.request_content_type == 'NONE'
    assert json.loads(parsed.params) == {'a': '1', 'b': '2'}


def test_parse_post_json(flask_app):
  with flask_app.test_request_context(
      '/api/x', method='POST', data=json.dumps({'k': 'v'}), content_type='application/json'):
    parsed = parse_flask_request(request, 'api/x', _params_json)
    assert parsed.request_content_type == 'APPLICATION_JSON'
    assert json.loads(parsed.params) == {'k': 'v'}


def test_parse_post_form(flask_app):
  with flask_app.test_request_context(
      '/api/x', method='POST', data={'f': '1'}, content_type='application/x-www-form-urlencoded'):
    parsed = parse_flask_request(request, 'api/x', _params_json)
    assert parsed.request_content_type == 'APPLICATION_X_WWW_FORM_URLENCODED'
    assert json.loads(parsed.params) == {'f': '1'}


def test_parse_post_multipart(flask_app):
  with flask_app.test_request_context(
      '/api/x', method='POST',
      data={'f': '1', 'file': (io.BytesIO(b'file-content'), 'a.bin')},
      content_type='multipart/form-data'):
    parsed = parse_flask_request(request, 'api/x', _params_json)
    assert parsed.request_content_type == 'MULTIPART_FORM_DATA'
    params = json.loads(parsed.params)
    assert params['f'] == '1'
    assert params['file'] == f'file-{create_md5(b"file-content")}'


def test_parse_post_unknown_ct(flask_app):
  with flask_app.test_request_context(
      '/api/x', method='POST', data='raw-body', content_type='text/plain'):
    parsed = parse_flask_request(request, 'api/x', _params_json)
    assert parsed.request_content_type == 'NONE'
    assert json.loads(parsed.params) == {}


# ---------- handle ----------


def test_handle_miss_404(make_handler, flask_app):
  handler = make_handler()
  with flask_app.test_request_context():
    resp, status = handler.handle('GET', '/nope', 'NONE', '{}')
    assert status == 404
    assert resp.get_json() == {'error': 'No valid mock data'}


def test_handle_hit_main_response(make_handler, flask_app, mock_db):
  aid = mock_db.insert_api({'url': '/api/x', 'method': 'GET', 'response': '{"hello": 1}'})['id']
  handler = make_handler()
  rk = handler.get_request_key('/api/x', 'GET', 'NONE')
  resk = handler.get_response_key('GET', 'NONE', '{}')
  handler.mock_api_map = {rk: {resk: _meta(api_data_id=aid)}}
  with flask_app.test_request_context():
    resp = handler.handle('GET', '/api/x', 'NONE', '{}')
    assert resp.get_json() == {'hello': 1}


def test_handle_variant_first_hit(make_handler, flask_app, mock_db):
  aid = mock_db.insert_api({'url': '/api/x', 'method': 'GET', 'response': '{"main": 1}'})['id']
  vid = mock_db.insert_variant({'api_data_id': aid, 'name': 'v1', 'response': '{"v": 1}'})['id']
  handler = make_handler()
  rk = handler.get_request_key('/api/x', 'GET', 'NONE')
  resk = handler.get_response_key('GET', 'NONE', '{}')
  handler.mock_api_map = {
    rk: {resk: _meta(api_data_id=aid, variants=[{'id': vid, 'timeout': 0}])},
  }
  state_result = {'device_id': 'dev1', 'state': {}, 'is_new': True}
  with flask_app.test_request_context():
    resp = handler.handle('GET', '/api/x', 'NONE', '{}', state_result=state_result)
    assert resp.get_json() == {'v': 1}   # 首命中变体而非主响应


# ---------- register_system_routes ----------


def _system_client(flask_app):
  calls = []
  register_system_routes(
    app=flask_app,
    server_name='TEST',
    on_shutdown=lambda: calls.append(1),
    logger=MOCK_LOGGER,
  )
  return flask_app.test_client(), calls


def test_ping(flask_app):
  client, _ = _system_client(flask_app)
  resp = client.get('/ping')
  assert resp.status_code == 200
  assert resp.get_json() == {'data': 'pong!'}


def test_shutdown_get_405(flask_app):
  client, _ = _system_client(flask_app)
  assert client.get(f'{SYSTEM_ROUTE}/shutdown').status_code == 405


def test_shutdown_loopback_invokes_callback(flask_app):
  client, calls = _system_client(flask_app)
  resp = client.post(f'{SYSTEM_ROUTE}/shutdown')
  assert resp.status_code == 200
  deadline = time.time() + 3
  while not calls and time.time() < deadline:
    time.sleep(0.1)
  assert calls == [1]


def test_shutdown_non_loopback_403(flask_app):
  client, calls = _system_client(flask_app)
  resp = client.post(f'{SYSTEM_ROUTE}/shutdown', environ_base={'REMOTE_ADDR': '10.0.0.9'})
  assert resp.status_code == 403
  assert calls == []
