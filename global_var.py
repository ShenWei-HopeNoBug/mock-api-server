# -*- coding: utf-8 -*-
from decorate import error_catch
from lib.system_lib import GLOBALS_CONFIG_MANAGER

# 版本号
version = 'v0.0.2'


def init():
  GLOBALS_CONFIG_MANAGER.init(replace=True)


@error_catch(error_msg='查找全局变量失败！', error_return=None)
def get_global_var(key=''):
  return GLOBALS_CONFIG_MANAGER.get(key=key)


@error_catch(error_msg='更新全局变量失败！')
def update_global_var(key='', value=None):
  GLOBALS_CONFIG_MANAGER.set(key=key, value=value)
