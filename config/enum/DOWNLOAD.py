# -*- coding: utf-8 -*-

# 最小下载连接超时时间(s)
MIN_CONNECT_TIMEOUT = 5
# 最大下载连接超时时间(s)
MAX_CONNECT_TIMEOUT = 300
# 动态调整最小下载连接超时时间(s)
DYNAMIC_MIN_CONNECT_TIMEOUT = 20
# 连续下载连接超时次数限制，达到这个限制会直接将连接超时设置为最小值
CONNECT_ERROR_LIMIT = 5
# 连续下载连接超时最大次数限制，达到这个限制直接判断为该类域名的资源不可下载，会将连接超时设置为很小的值快速跳过该类域名的资源下载
CONNECT_ERROR_MAX_LIMIT = 10
# 下载读取超时时间
READ_TIMEOUT = 300
