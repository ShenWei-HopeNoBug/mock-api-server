# -*- coding: utf-8 -*-

# ---------------------------------------------------
# Mock服务参数匹配模式枚举
# HTTP_PARAMS_SIMPLE_MATCH: 简单匹配模式，直接匹配 params JSON 字符串,不处理数据 key 的乱序问题
# HTTP_PARAMS_EXACT_MATCH: 精确匹配模式，匹配 params 参数时精确匹配，处理数据 key 的乱序问题
# ---------------------------------------------------
HTTP_PARAMS_SIMPLE_MATCH = 0
HTTP_PARAMS_EXACT_MATCH = 1

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
}
