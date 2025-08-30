# -*- coding: utf-8 -*-
import math
from PyQt5.QtWidgets import QApplication


def get_webview_dialog_config() -> dict:
  primary_screen = QApplication.primaryScreen()
  primary_screen_size = primary_screen.size()
  primary_width = primary_screen_size.width()
  primary_height = primary_screen_size.height()
  vw = primary_width
  vh = primary_height - 240
  width = 1920
  height = 1080
  zoom = 1
  if width <= vw:
    height = min(height, vh)
    zoom = vw / width
  else:
    width = vw
    height = vh

  width = width - 240
  x0 = math.floor((primary_width - width) * 0.5)
  y0 = math.floor((primary_height - height) * 0.5)

  return {
    "x0": x0,
    "y0": y0,
    "width": width,
    "height": height,
    "zoom": zoom,
  }
