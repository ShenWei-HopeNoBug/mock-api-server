# -*- coding: utf-8 -*-
from decorate import error_catch
from lib.system_lib import HISTORY_CONFIG_MANAGER


def init():
  HISTORY_CONFIG_MANAGER.init()


@error_catch(error_msg='查找历史数据失败！', error_return=None)
def get_history_var(key=''):
  HISTORY_CONFIG_MANAGER.get(key=key)


@error_catch(error_msg='更新历史数据失败！')
def update_history_var(key='', value=None):
  HISTORY_CONFIG_MANAGER.set(key=key, value=value)
