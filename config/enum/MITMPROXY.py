# -*- coding: utf-8 -*-

from lib.utils_lib import (generate_uuid, JsonFormat)

# 脚本抓包数据字段配置
MITMPROXY_DATA_FIELDS = [
  {
    "key": "id",
    "default_callback": generate_uuid,
  },
  {
    "key": "type",
    "default_callback": lambda: "MITMPROXY"
  },
  {
    "key": "url",
    "default_callback": lambda: "",
  },
  {
    "key": "method",
    "default_callback": lambda: "",
  },
  {
    "key": "params",
    "default_callback": lambda: JsonFormat.dumps({}),
  },
  {
    "key": "response",
    "default_callback": lambda: JsonFormat.dumps({}),
  },
]
