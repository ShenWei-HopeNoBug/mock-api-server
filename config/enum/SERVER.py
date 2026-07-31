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
  'timeout': 0,
  'request_content_type': 'NONE',
}
