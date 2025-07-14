# -*- coding: utf-8 -*-
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from lib.utils_lib import JsonFormat


class TInteractObj(QObject):
  js2qt_signal = pyqtSignal(str)
  qt2js_signal = pyqtSignal(str)

  def __init__(self, parent=None):
    super().__init__(parent)

  @pyqtSlot(str)
  def send_js2qt_msg(self, message: str):
    self.js2qt_signal.emit(message)

  @pyqtSlot(str)
  def send_qt2js_msg(self, message: str):
    self.qt2js_signal.emit(message)

  @pyqtSlot(str)
  def send_qt2js_dict_msg(self, data: dict):
    if type(data) != dict:
      return

    self.send_qt2js_msg(JsonFormat.format_dict_to_json_string(data))
