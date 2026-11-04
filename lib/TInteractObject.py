# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from app_types.qt_bridge_types import JsonValue, QtResponsePayload
from lib.utils_lib import JsonFormat


class TInteractObj(QObject):
  js2qt_signal = Signal(str)
  qt2js_signal = Signal(str)

  def __init__(self, parent: Optional[QObject] = None) -> None:
    super().__init__(parent)

  @Slot(str)
  def send_js2qt_msg(self, message: str) -> None:
    self.js2qt_signal.emit(message)

  @Slot(str)
  def send_qt2js_msg(self, message: str) -> None:
    self.qt2js_signal.emit(message)

  # TODO(qt-bridge): @Slot(str) 与 QtResponsePayload dict 参数声明不一致，待评估修正
  @Slot(str)
  def send_qt2js_dict_msg(self, data: QtResponsePayload) -> None:
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
