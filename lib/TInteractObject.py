# -*- coding: utf-8 -*-
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from lib.utils_lib import JsonFormat
from app_types.qt_bridge_types import JsonValue, QtResponsePayload


class TInteractObj(QObject):
  js2qt_signal = pyqtSignal(str)
  qt2js_signal = pyqtSignal(str)

  def __init__(self, parent: Optional[QObject] = None) -> None:
    super().__init__(parent)

  @pyqtSlot(str)
  def send_js2qt_msg(self, message: str) -> None:
    self.js2qt_signal.emit(message)

  @pyqtSlot(str)
  def send_qt2js_msg(self, message: str) -> None:
    self.qt2js_signal.emit(message)

  @pyqtSlot(str)
  def send_qt2js_dict_msg(self, data: dict) -> None:
    if not isinstance(data, dict):
      return

    self.send_qt2js_msg(JsonFormat.dumps(data))

  @staticmethod
  def build_qt_response(
      name: str,
      action_id: str,
      data: JsonValue = None,
      status_code: int = 0,
      status_msg: str = '',
  ) -> QtResponsePayload:
    return {
      "type": "response",
      "name": name,
      "action_id": action_id or '',
      "status_code": status_code,
      "status_msg": status_msg,
      "data": data,
    }
