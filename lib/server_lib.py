# -*- coding: utf-8 -*-

from lib.decorate import error_catch
from lib.app_lib import _get_mock_db


# 读取 static 数据
@error_catch(error_msg='读取 static 数据失败', error_return=[])
def get_static_data_list(work_dir='.') -> list:
  mock_db = _get_mock_db(work_dir)
  return mock_db.get_static_list()
