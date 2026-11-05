# -*- coding: utf-8 -*-
import hashlib
import socket
from collections import namedtuple

import pytest

from app_types.request_types import RequestContentType
from lib.utils_lib import (
  JsonFormat,
  create_md5,
  get_request_content_type,
  get_url_domain,
  is_file_request,
  is_local_port_occupied,
  is_url_match,
  limit_num_range,
  remove_byte_empty_content,
  remove_url_domain,
  remove_url_query,
)

# ---------- create_md5 ----------


def test_md5_str_and_bytes_equal():
  assert create_md5('abc') == hashlib.md5(b'abc').hexdigest()
  assert create_md5(b'abc') == create_md5('abc')


def test_md5_default_empty():
  assert create_md5() == hashlib.md5(b'').hexdigest()


def test_md5_differs():
  assert create_md5('a') != create_md5('b')


# ---------- is_url_match（includes 为正则） ----------


def test_url_match_str_pattern():
  assert is_url_match('https://a.com/x', 'a\\.com') is True
  assert is_url_match('https://a.com/x', 'b\\.com') is False


def test_url_match_list_pattern():
  assert is_url_match('https://a.com/x', ['b\\.com', 'a\\.com']) is True
  assert is_url_match('https://a.com/x', ['b\\.com']) is False


def test_url_match_empty_or_bad_inputs():
  assert is_url_match('', 'x') is False
  assert is_url_match('https://a.com', []) is False
  assert is_url_match('https://a.com', {'a': 1}) is False


# ---------- url helpers ----------


def test_get_url_domain():
  assert get_url_domain('https://a.com:8080/x?q=1') == 'a.com:8080'
  assert get_url_domain('http://a.com/') == 'a.com'
  assert get_url_domain('no-scheme.com/x') == ''


def test_remove_url_domain():
  assert remove_url_domain('https://a.com/x/y?q=1') == '/x/y'
  assert remove_url_domain('https://a.com') == ''


def test_remove_url_query():
  assert remove_url_query('/api/x?a=1&b=2') == '/api/x'
  assert remove_url_query('/api/x') == '/api/x'


# ---------- get_request_content_type ----------


def test_ct_non_post_always_none():
  assert get_request_content_type('application/json', 'GET') == RequestContentType.NONE
  assert get_request_content_type('multipart/form-data', 'DELETE') == RequestContentType.NONE


def test_ct_post_mapping():
  assert (get_request_content_type('application/json; charset=utf-8', 'POST')
          == RequestContentType.APPLICATION_JSON)
  assert (get_request_content_type('application/x-www-form-urlencoded', 'POST')
          == RequestContentType.APPLICATION_X_WWW_FORM_URLENCODED)
  assert (get_request_content_type('multipart/form-data; boundary=x', 'POST')
          == RequestContentType.MULTIPART_FORM_DATA)


def test_ct_post_unknown_or_empty():
  assert get_request_content_type('text/plain', 'POST') == RequestContentType.NONE
  assert get_request_content_type('', 'POST') == RequestContentType.NONE


def test_ct_case_insensitive():
  assert get_request_content_type('Application/JSON', 'POST') == RequestContentType.APPLICATION_JSON


# ---------- is_file_request ----------


def test_is_file_request():
  assert is_file_request('https://a.com/static/a.png') is True
  assert is_file_request('https://a.com/static/a.png?v=1') is True
  assert is_file_request('https://a.com/api/users') is False
  assert is_file_request('https://a.com') is False


def test_is_file_request_edge():
  assert is_file_request('') is False
  assert is_file_request('nodot') is False


# ---------- remove_byte_empty_content ----------


def test_remove_byte_empty():
  assert remove_byte_empty_content(b'a\nb\rc\td') == b'abcd'
  assert remove_byte_empty_content(b'abc') == b'abc'


def test_remove_byte_empty_non_bytes_passthrough():
  assert remove_byte_empty_content('a\nb') == 'a\nb'


# ---------- JsonFormat ----------


def test_json_dumps_chinese():
  assert JsonFormat.dumps({'k': '中文'}) == '{"k": "中文"}'


def test_json_format_roundtrip():
  assert JsonFormat.format_json_string('{"b":1,"a":2}') == '{"b": 1, "a": 2}'


def test_json_sort():
  assert JsonFormat.sort_dumps({'b': 1, 'a': 2}) == '{"a": 2, "b": 1}'
  assert JsonFormat.format_and_sort_json_string('{"b":1,"a":2}') == '{"a": 2, "b": 1}'
  assert JsonFormat.format_and_sort_dict({'b': 1, 'a': 2}) == {'a': 2, 'b': 1}


# ---------- limit_num_range ----------


def test_limit_num_range():
  assert limit_num_range(5, 0, 10) == 5
  assert limit_num_range(-1, 0, 10) == 0
  assert limit_num_range(11, 0, 10) == 10
  assert limit_num_range(0.5, 0.0, 1.0) == 0.5


# ---------- is_local_port_occupied（双地址族探测） ----------

_Addr = namedtuple('addr', ['ip', 'port'])
_Conn = namedtuple('conn', ['status', 'laddr'])


def _patch_connections(monkeypatch, rows):
  """往 psutil.net_connections 注入假监听行"""
  import lib.utils_lib as ul

  monkeypatch.setattr(ul.psutil, 'net_connections', lambda kind='tcp': rows)


@pytest.mark.parametrize('squat_ip', ['0.0.0.0', '127.0.0.1', '::', '::1'])
def test_port_occupied_detects_all_listen_families(monkeypatch, squat_ip):
  # 通配/回环任一地址占坑都会劫持或阻塞本地服务，全部要探出
  _patch_connections(monkeypatch, [_Conn('LISTEN', _Addr(squat_ip, 8080))])
  assert is_local_port_occupied(8080) is True


def test_port_occupied_nic_squat_ignored(monkeypatch):
  # 具体网卡 IP 占坑只劫该网卡流量，回环不受影响 → 既定漏报边界
  _patch_connections(monkeypatch, [_Conn('LISTEN', _Addr('192.168.1.10', 8080))])
  assert is_local_port_occupied(8080) is False


def test_port_occupied_other_port_or_state_ignored(monkeypatch):
  _patch_connections(monkeypatch, [
    _Conn('LISTEN', _Addr('0.0.0.0', 9090)),        # 别的端口
    _Conn('TIME_WAIT', _Addr('127.0.0.1', 8080)),   # 非 LISTEN 状态
    _Conn('LISTEN', ()),                            # 空 laddr
  ])
  assert is_local_port_occupied(8080) is False


def test_port_occupied_real_socket_loopback():
  # 真实 socket 自测：本进程绑 127.0.0.1 回环口应被探出
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.bind(('127.0.0.1', 0))
  sock.listen(1)
  try:
    port = sock.getsockname()[1]
    assert is_local_port_occupied(port) is True
  finally:
    sock.close()
