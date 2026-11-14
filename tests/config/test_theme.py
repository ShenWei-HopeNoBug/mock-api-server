# -*- coding: utf-8 -*-
import pytest

from config.theme import PALETTE, c, qss

# ---------- PALETTE 值域 ----------


def test_palette_values_in_range():
  for name, v in PALETTE.items():
    assert len(v) in (3, 4), name
    assert all(isinstance(x, int) and 0 <= x <= 255 for x in v), name


# ---------- c() ----------


def test_c_rgb():
  assert c('TEXT') == 'rgb(96, 62, 30)'


def test_c_rgba():
  assert c('CARD_BG') == 'rgba(255, 250, 238, 150)'


def test_c_unknown_token_raises():
  with pytest.raises(KeyError):
    c('NOPE')


# ---------- qss() ----------


def test_qss_substitute():
  assert qss('color:$TEXT;') == 'color:rgb(96, 62, 30);'


def test_qss_multi_token():
  out = qss('a{color:$TEXT;background-color:$PANEL_BG;}')
  assert out == 'a{color:rgb(96, 62, 30);background-color:rgb(255, 248, 225);}'


def test_qss_unknown_token_raises():
  with pytest.raises(KeyError):
    qss('color:$NOPE;')


# ---------- 导出片段无占位符残留 ----------


def test_style_fragments_fully_rendered():
  import qt_ui.common_style as common_style
  from qt_ui.main_win import main_win_style
  from qt_win.pet_shell import PET_MENU_STYLE

  fragments = [
    v for k, v in vars(common_style).items()
    if k.isupper() and isinstance(v, str)
  ] + [main_win_style.window, main_win_style.tooltip, PET_MENU_STYLE]
  assert fragments
  for frag in fragments:
    assert '$' not in frag
