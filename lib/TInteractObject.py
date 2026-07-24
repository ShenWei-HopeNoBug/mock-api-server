# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from lib.utils_lib import JsonFormat


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
  def send_qt2js_dict_msg(self, data: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
      return

    self.send_qt2js_msg(JsonFormat.dumps(data))
