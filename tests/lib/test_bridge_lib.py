# -*- coding: utf-8 -*-
import json
import threading
import time

from config.enum.BIZ_CODE import BIZ_PARAM_INVALID, BIZ_SUCCESS
from lib.bridge_lib import BridgeDispatcher, _unpack_result


def _req(name='/x', action_id='a1', params=None):
  return json.dumps({
    'type': 'request',
    'name': name,
    'action_id': action_id,
    'params': params if params is not None else {},
  })


def _wait_len(items, n, timeout=3):
  deadline = time.time() + timeout
  while len(items) < n and time.time() < deadline:
    time.sleep(0.02)


def _make_bridge(**kw):
  args = {'send': lambda p: None, 'request_handlers': {}, 'handler_context': None, 'tag': 't'}
  args.update(kw)
  return BridgeDispatcher(**args)


# ---------- _unpack_result ----------


def test_unpack_success_strips_status_keys():
  r = _unpack_result({'status_code': BIZ_SUCCESS, 'status_msg': 'ok', 'list': [1]})
  assert r.status_code == BIZ_SUCCESS
  assert r.data == {'list': [1]}


def test_unpack_success_empty_data_none():
  r = _unpack_result({'status_code': BIZ_SUCCESS, 'status_msg': 'ok'})
  assert r.data is None


def test_unpack_fail():
  r = _unpack_result({'status_code': -30001, 'status_msg': '数据不存在'})
  assert r.status_code == -30001
  assert r.status_msg == '数据不存在'
  assert r.data is None


def test_unpack_passthrough():
  assert _unpack_result([1, 2]).data == [1, 2]
  assert _unpack_result(None).data is None


# ---------- FIFO / 队列 / 关闭 ----------


def test_fifo_order():
  order = []

  def handler(ctx, params):
    order.append(params['n'])
    return {'status_code': 0}

  bridge = _make_bridge(request_handlers={'/x': handler})
  for i in range(20):
    bridge.dispatch(_req(params={'n': i}))
  bridge.shutdown()
  bridge._worker.join(timeout=5)
  assert order == list(range(20))


def test_response_payload_shape():
  sent = []
  bridge = _make_bridge(
    send=sent.append,
    request_handlers={'/echo': lambda ctx, params: {'status_code': 0, 'status_msg': '', 'echo': params}},
  )
  bridge.dispatch(_req(name='/echo', action_id='a9', params={'k': 1}))
  _wait_len(sent, 1)
  bridge.shutdown()
  assert sent[0]['type'] == 'response'
  assert sent[0]['name'] == '/echo'
  assert sent[0]['action_id'] == 'a9'
  assert sent[0]['status_code'] == BIZ_SUCCESS
  assert sent[0]['data'] == {'echo': {'k': 1}}


def test_unknown_path_param_invalid():
  sent = []
  bridge = _make_bridge(send=sent.append)
  bridge.dispatch(_req(name='/nope', action_id='a2'))
  _wait_len(sent, 1)
  bridge.shutdown()
  assert sent[0]['status_code'] == BIZ_PARAM_INVALID


def test_shutdown_drains_queue():
  done = []

  def slow(ctx, params):
    time.sleep(0.05)
    done.append(params['n'])
    return {'status_code': 0}

  bridge = _make_bridge(request_handlers={'/x': slow})
  for i in range(5):
    bridge.dispatch(_req(params={'n': i}))
  bridge.shutdown()
  bridge._worker.join(timeout=10)
  assert done == [0, 1, 2, 3, 4]   # 已入队消息排空后 worker 才退出


def test_dispatch_after_shutdown_dropped():
  bridge = _make_bridge()
  bridge.shutdown()
  bridge._worker.join(timeout=5)
  bridge.dispatch(_req())
  assert bridge._dropped_count == 1


def test_queue_full_drops_new_and_shutdown_nonblocking():
  gate = threading.Event()

  def blocked(ctx, params):
    gate.wait(5)
    return {'status_code': 0}

  bridge = _make_bridge(request_handlers={'/x': blocked})
  bridge.dispatch(_req())          # worker 取走后阻塞在 gate
  time.sleep(0.1)                  # 确保 worker 已取走首条
  for _ in range(600):
    bridge.dispatch(_req())
  assert bridge._dropped_count == 88   # 512 入队，其余丢弃
  gate.set()
  t0 = time.monotonic()
  bridge.shutdown()                # 队满时挤位放 poison pill，非阻塞
  assert time.monotonic() - t0 < 1
  bridge._worker.join(timeout=10)
  assert not bridge._worker.is_alive()


def test_send_response_skipped_after_close():
  sent = []
  bridge = _make_bridge(send=sent.append)
  bridge.shutdown()
  bridge._worker.join(timeout=5)
  bridge._send_response('/x', 'a1', {}, BIZ_SUCCESS, '')
  assert sent == []


def test_event_dedup():
  calls = []
  bridge = _make_bridge(
    event_handlers={'sync': lambda ctx, msg: calls.append(msg['action_id'])},
  )
  msg = json.dumps({'type': 'event', 'name': 'sync', 'action_id': 'e1'})
  bridge.dispatch(msg)
  bridge.dispatch(msg)
  _wait_len(calls, 1)
  time.sleep(0.2)
  bridge.shutdown()
  assert calls == ['e1']   # 相同 (name, action_id) 去重
