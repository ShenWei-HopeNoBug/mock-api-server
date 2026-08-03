# -*- coding: utf-8 -*-

# ---------------------------------------------------
# API 数据写入默认值
# insert_api 等方法在 record 字段缺失时使用这些默认值
# ---------------------------------------------------
API_INSERT_DEFAULTS = {
  'type': 'MITMPROXY',
  'url': '',
  'method': 'GET',
  'params': '{}',
  'response': '{}',
  'response_variant_ids': '[]',
  'enabled': True,
  'timeout': 0,
  'request_content_type': 'NONE',
}

# ---------------------------------------------------
# API response 变体写入默认值
# insert_variant 等方法在 record 字段缺失时使用这些默认值
# ---------------------------------------------------
API_RESPONSE_VARIANT_INSERT_DEFAULTS = {
  'name': '',
  'response': '{}',
  'enabled': True,
}
