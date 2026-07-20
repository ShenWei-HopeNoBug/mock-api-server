# -*- coding: utf-8 -*-
from lib.utils_lib import (
  JsonFormat,
  create_md5,
  error_catch,
)


# 保存抓包数据到缓存
@error_catch(error_msg='保存抓包数据到缓存失败')
def save_response_to_cache(record: dict, cache: dict) -> None:
  url: str = record.get('url', '')
  method: str = record.get('method', '')
  params: str = record.get('params', JsonFormat.dumps({}))

  # 这里的 params 数据做下键名排序，便于相同参数key乱序进行去重匹配
  sort_params: str = JsonFormat.format_and_sort_json_string(params)

  secret_key = r'{}{}'.format(method, sort_params)
  md5_key = create_md5(secret_key)
  search_key = r'{}{}'.format(url, method)
  # 创建新 url 的答案映射 dict
  if search_key not in cache:
    cache[search_key] = {}

  # 添加新的请求 response 内容
  cache[search_key][md5_key] = record


# 保存静态资源数据到缓存
def save_static_to_cache(record: dict, cache: dict) -> None:
  url = record.get('url', '')
  if not url:
    return
  search_key = create_md5(url)
  cache[search_key] = record
