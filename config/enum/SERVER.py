# -*- coding: utf-8 -*-

# ---------------------------------------------------
# Mock 服务读取数据默认值
# create_api_dict 遍历 mock 数据时字段缺失使用这些默认值兜底
# ---------------------------------------------------
MOCK_API_DATA_DEFAULTS = {
  'type': 'MITMPROXY',
  'url': '',
  'method': 'GET',
  'params': '{}',
  'response': '{}',
  'response_variant_ids': [],
  'enabled': True,
  'timeout': 0,
  'request_content_type': 'NONE',
}

# ---------------------------------------------------
# Mock 服务运行时常量
# ---------------------------------------------------
# 静态资源匹配缓存上限
STATIC_MATCH_CACHE_LIMIT = 1000
# mock 接口响应缓存上限（按条目数）
RESPONSE_CACHE_LIMIT = 200
# 静态资源返回最大延时（秒）
STATIC_MATCH_MAX_DELAY_SECONDS = 120

# 设备标识 Header 名称
DEVICE_ID_HEADER = 'Mock-Server-Device-Id'
# 客户端状态内存存储上限
DEVICE_STATE_LIMIT = 1000
