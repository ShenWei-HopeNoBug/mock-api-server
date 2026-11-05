# -*- coding: utf-8 -*-
import os

import pytest

from lib.static_file_lib import StaticFileHandler
from lib.throttle_lib import create_throttle


@pytest.fixture()
def static(tmp_path):
  """tmp 下静态目录 + handler 实例（关限速，不走节流路径）"""
  folder = tmp_path / 'static'
  folder.mkdir()
  (folder / 'a.txt').write_text('hello', encoding='utf-8')
  (folder / 'a.png').write_bytes(b'\x89PNG')
  return StaticFileHandler(
    work_dir=str(tmp_path), static_load_speed=0, static_folder='static', max_delay=5)


# ---------- _parse_range ----------


@pytest.mark.parametrize(
  'header,total,expected',
  [
    (None, 100, None),                 # 无 Range 头
    ('bytes=0-9', 0, None),            # 空文件
    ('bytes=0-99', 1000, (0, 99)),
    ('bytes=0-', 1000, (0, 999)),      # 到文件末尾
    ('bytes=-500', 1000, (500, 999)),  # suffix
    ('bytes=-2000', 1000, (0, 999)),   # suffix 超文件大小从头
    ('bytes=0-2000', 1000, (0, 999)),  # end 超界截断
    ('bytes=1500-', 1000, None),       # start 越界
    ('bytes=500-400', 1000, None),     # start > end（截断后区间为空）
    ('bytes=-0', 1000, None),          # suffix=0
    ('bytes=-', 1000, None),           # 两端均空
    ('items=0-99', 1000, None),        # 非 bytes 单位
    ('bytes=abc-def', 1000, None),     # 畸形
  ],
)
def test_parse_range(header, total, expected):
  assert StaticFileHandler._parse_range(header, total) == expected


# ---------- _resolve_file ----------


def test_resolve_normal(static):
  r = static._resolve_file('/a.txt')
  assert r['valid'] is True
  assert r['file_name'] == 'a.txt'


def test_resolve_traversal_nonfile_404(static):
  r = static._resolve_file('/../../etc/passwd')
  assert r['valid'] is False
  assert r['result'][1] == 404


def test_resolve_traversal_falls_back_basename(static):
  # basename 剥掉 ../ 后命中 static 内同名文件，不发生目录逃逸
  r = static._resolve_file('/../a.txt')
  assert r['valid'] is True
  assert r['file_name'] == 'a.txt'


def test_resolve_missing_404(static):
  r = static._resolve_file('/nope.txt')
  assert r['valid'] is False
  assert r['result'][1] == 404


def test_resolve_nonfile_path_404(static):
  r = static._resolve_file('/api/users')
  assert r['valid'] is False
  assert r['result'][1] == 404


def test_resolve_symlink_escape_403(static, tmp_path):
  outside = tmp_path / 'secret.txt'
  outside.write_text('x', encoding='utf-8')
  try:
    os.symlink(str(outside), os.path.join(static.static_folder, 'link.txt'))
  except OSError:
    pytest.skip('无权限创建符号链接')
  r = static._resolve_file('/link.txt')
  assert r['valid'] is False
  assert r['result'][1] == 403


# ---------- etag / 条件请求 / 缓存头 ----------


def _stat_a_txt(static):
  return os.stat(os.path.join(static.static_folder, 'a.txt'))


def test_compute_etag_format():
  assert StaticFileHandler._compute_etag(1024, 1700000000.5) == '"1024-1700000000500"'


def test_is_image():
  assert StaticFileHandler._is_image('a.png') is True
  assert StaticFileHandler._is_image('a.txt') is False


def test_format_size():
  assert StaticFileHandler._format_size(500) == '500B'
  assert StaticFileHandler._format_size(2048) == '2.00KB'
  assert StaticFileHandler._format_size(5 * 1024 * 1024) == '5.00MB'


def test_format_http_date():
  assert StaticFileHandler._format_http_date(1700000000).endswith('GMT')


def test_cache_control_by_type(static):
  img = static._build_cache_control('a.png')
  assert img.startswith('public, max-age=')
  assert 'must-revalidate' not in img
  assert static._build_cache_control('a.txt') == 'public, max-age=0, must-revalidate'


def test_cache_hit_etag_strong_and_weak(static):
  stat = _stat_a_txt(static)
  f = os.path.join(static.static_folder, 'a.txt')
  etag = StaticFileHandler._compute_etag(stat.st_size, stat.st_mtime)
  assert static._check_cache_hit(f, {'If-None-Match': etag}, stat) is True
  # 弱 ETag 归一化后视为等价
  assert static._check_cache_hit(f, {'If-None-Match': f'W/{etag}'}, stat) is True
  assert static._check_cache_hit(f, {'If-None-Match': '"other"'}, stat) is False


def test_cache_hit_star(static):
  stat = _stat_a_txt(static)
  f = os.path.join(static.static_folder, 'a.txt')
  assert static._check_cache_hit(f, {'If-None-Match': '*'}, stat) is True


def test_cache_hit_if_modified_since(static):
  stat = _stat_a_txt(static)
  f = os.path.join(static.static_folder, 'a.txt')
  future = StaticFileHandler._format_http_date(stat.st_mtime + 3600)
  past = StaticFileHandler._format_http_date(stat.st_mtime - 3600)
  assert static._check_cache_hit(f, {'If-Modified-Since': future}, stat) is True
  assert static._check_cache_hit(f, {'If-Modified-Since': past}, stat) is False


def test_if_range(static):
  stat = _stat_a_txt(static)
  etag = StaticFileHandler._compute_etag(stat.st_size, stat.st_mtime)
  assert static._check_if_range(stat, {}) is True                        # 无 If-Range 放行
  assert static._check_if_range(stat, {'If-Range': etag}) is True        # ETag 强比较命中
  assert static._check_if_range(stat, {'If-Range': f'W/{etag}'}) is False  # 弱 ETag 拒绝
  assert static._check_if_range(stat, {'If-Range': '"other"'}) is False


# ---------- _should_use_throttled / 无策略降级 ----------


def test_should_use_throttled_requires_strategy(tmp_path):
  # 限速开启但无策略实例（策略名非法/未注入）→ False，降级 direct 不限速
  handler = StaticFileHandler(
    work_dir=str(tmp_path), static_load_speed=100, static_folder='static', max_delay=5)
  assert handler._should_use_throttled() is False


def test_should_use_throttled_with_strategy(tmp_path):
  # 限速开启 + 有效策略实例 → True，走节流路径
  throttle = create_throttle('CHUNK_SLEEP', speed_kbps=100, max_delay=5)
  handler = StaticFileHandler(
    work_dir=str(tmp_path), static_load_speed=100, static_folder='static',
    max_delay=5, throttle_strategy=throttle)
  assert handler._should_use_throttled() is True


def test_match_no_throttle_degrades_to_direct(static, tmp_path, flask_app):
  # 限速开启但无策略实例时 match() 走 direct 正常出文件，不抛 AttributeError
  handler = StaticFileHandler(
    work_dir=str(tmp_path), static_load_speed=100, static_folder='static', max_delay=5)
  with flask_app.test_request_context('/a.txt'):
    resp = handler.match('a.txt', {})
  assert resp.status_code == 200
