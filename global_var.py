# -*- coding: utf-8 -*-
from decorate import error_catch
from lib.system_lib import GLOBALS_CONFIG_MANAGER

# 版本号
version = 'v0.0.2'
'''
mitmproxy 抓包默认配置
include_path: 抓包链接要包含的文本内容
static_include_path: 抓包静态资源链接要包含的文本内容
'''
mitmproxy_config = {
  "include_path": "www.baidu.com",
  "static_include_path": []
}

'''
mock 服务的配置
include_files: 启动服务后要动态替换的静态资源链接扩展名列表
static_match_route: 动态匹配静态资源请求的路由
'''
mock_server_config = {
  "include_files": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
  "static_match_route": []
}

# 存放数据文件的目录
data_dir_path = r'/data'
# 存放配置文件的目录
config_dir_path = r'/config'
# 存放系统文件的目录
system_dir_path = r'./system'


def init():
  GLOBALS_CONFIG_MANAGER.init()


@error_catch(error_msg='查找全局变量失败！', error_return=None)
def get_global_var(key=''):
  GLOBALS_CONFIG_MANAGER.get(key=key)


@error_catch(error_msg='更新全局变量失败！')
def update_global_var(key='', value=None):
  GLOBALS_CONFIG_MANAGER.set(key=key, value=value)
