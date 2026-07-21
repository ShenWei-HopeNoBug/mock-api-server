# -*- coding: utf-8 -*-

from lib.decorate import error_catch
from lib.db_lib import MockDBCache


# 读取 static 数据
@error_catch(error_msg='读取 static 数据失败', error_return=[])
def get_static_data_list(work_dir='.') -> list:
  mock_db = MockDBCache.get(work_dir)
  return mock_db.get_static_list()
