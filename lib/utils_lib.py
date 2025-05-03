# -*- coding: utf-8 -*-
import os
import json
import copy
from utils import (check_and_create_dir, JsonFormat)
from decorate import error_catch


class ConfigFileManager:
  def __init__(self, path: str, config: dict = {}):
    self.path = path
    self.config = copy.deepcopy(config)

  def init(self, replace: bool = False):
    work_dir = os.path.dirname(self.path)
    # 检查并创建系统文件夹
    check_and_create_dir(work_dir)

    # 不替换已经存在的文件
    if not replace and os.path.exists(self.path):
      return

    with open(self.path, 'w', encoding='utf-8') as fl:
      fl.write(JsonFormat.dumps(copy.deepcopy(self.config)))

  @error_catch(error_msg='查找变量失败！', error_return=None)
  def get(self, key: str):
    if not key:
      return None

    with open(self.path, 'r', encoding='utf-8') as fl:
      data = fl.read()
      dict_data: dict = json.loads(data)

    return dict_data.get(key, None)

  @error_catch(error_msg='更新变量失败！')
  def set(self, key: str, value):
    if not key:
      return

    with open(self.path, 'r', encoding='utf-8') as fl:
      data: str = fl.read()
      dict_data: dict = json.loads(data)
      dict_data[key] = value

    with open(self.path, 'w', encoding='utf-8') as fl:
      fl.write(JsonFormat.dumps(dict_data))
