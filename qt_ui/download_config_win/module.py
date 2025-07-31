# -*- coding: utf-8 -*-
import re

from PyQt5.QtWidgets import QMessageBox
from qt_ui.list_edit_module.module import ListEditModule


class FileTypeListModule(ListEditModule):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def check_edit_valid(
      self,
      text: str = '',
      old_text: str = '',
      is_edit: bool = False,
      current_list: list = None,
  ):
    valid = bool(re.match(r'^\.[a-zA-Z0-9]+$', text))
    if not valid:
      QMessageBox.critical(
        self,
        '异常',
        '请输入标准的文件扩展名文本（扩展名字符可包含大小写字母和数字），如：\n .jpg, .png',
      )

    return valid
