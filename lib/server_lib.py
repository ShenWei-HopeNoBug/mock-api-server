# -*- coding: utf-8 -*-

import os
import pandas as pd
from lib.decorate import error_catch
from config.work_file import STATIC_DATA_PATH


# 读取 static 数据
@error_catch(error_msg='读取 static 数据失败', error_return=[])
def get_static_data_list(work_dir='.') -> list:
  static_list = []
  static_data_path = r'{}{}'.format(work_dir, STATIC_DATA_PATH)
  if not os.path.exists(static_data_path):
    return []

  data = pd.read_json(static_data_path)
  # 行遍历
  for row_index, row_data in data.iterrows():
    static_list.append({
      "type": row_data.get('type'),
      "url": row_data.get('url'),
    })

  return static_list
