# -*- coding: utf-8 -*-

# 静态资源延时返回路由
STATIC_DELAY_ROUTE = r'/static_delay'
# 系统接口路由
SYSTEM_ROUTE = r'/system'
# mock 接口统一路由
MOCK_API_ROUTE = r'/api'
# 内置静态资源路由
STATIC_ROUTE = r'/static'

# 内置已占用命名的路由列表
INNER_ROUTE_LIST = [
  STATIC_DELAY_ROUTE,
  SYSTEM_ROUTE,
  MOCK_API_ROUTE,
  STATIC_ROUTE,
]
