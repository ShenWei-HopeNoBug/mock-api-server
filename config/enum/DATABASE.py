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
  'operator': '',
}

# ---------------------------------------------------
# 合法的 HTTP 方法枚举值
# mock 服务仅支持 GET 和 POST 两种请求方法
# ---------------------------------------------------
VALID_HTTP_METHODS = ('GET', 'POST')

# ---------------------------------------------------
# 合法的 request_content_type 枚举值
# GET 请求固定为 NONE；POST 请求可为以下四种值之一
# ---------------------------------------------------
VALID_REQUEST_CONTENT_TYPES = (
  'NONE',
  'APPLICATION_JSON',
  'MULTIPART_FORM_DATA',
  'APPLICATION_X_WWW_FORM_URLENCODED',
)

# ---------------------------------------------------
# API response 变体写入默认值
# insert_variant 等方法在 record 字段缺失时使用这些默认值
# ---------------------------------------------------
API_RESPONSE_VARIANT_INSERT_DEFAULTS = {
  'name': '',
  'response': '{}',
  'enabled': True,
  'timeout': 0,
  'operator': '',
}
