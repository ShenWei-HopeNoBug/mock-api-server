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
}
