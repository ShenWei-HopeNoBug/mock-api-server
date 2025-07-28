# -*- coding: utf-8 -*-
import re

from PyQt5.QtWidgets import QMessageBox
from qt_ui.list_edit_module.module import ListEditModule
from config.route import (INNER_ROUTE_LIST)


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


class StaticRouteListModule(ListEditModule):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def check_edit_valid(
      self,
      text: str = '',
      old_text: str = '',
      is_edit: bool = False,
      current_list: list = None,
  ) -> bool:
    valid: bool = bool(re.match(r'^/[a-zA-Z0-9_-]+$', text))
    if not valid:
      QMessageBox.critical(
        self,
        '异常',
        '请输入指定格式的路由（路由字符可包含大小写字母、数字、下划线和中划线），如：\n /test，/test2, /my_path',
      )

    inner_route_set = set(INNER_ROUTE_LIST)
    if text in inner_route_set:
      valid = False
      QMessageBox.critical(
        self,
        '异常',
        '该路由名已被应用内部服务占用，请不要使用以下路由进行命名：\n{}'.format('，'.join(INNER_ROUTE_LIST)),
      )

    return valid
