# -*- coding: utf-8 -*-
import os
import pandas as pd
from config.enum.MITMPROXY import MITMPROXY_DATA_FIELDS
from lib.app_lib import get_mitmproxy_api_data_list
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


# 读取本地抓包数据到cache
@error_catch(error_msg='读取本地抓包数据到cache异常', error_return={})
def load_response_cache(work_dir='.') -> dict:
  mitmproxy_data = get_mitmproxy_api_data_list(work_dir=work_dir)

  cache: dict = {}
  # 行遍历
  for row_data in mitmproxy_data:
    save_response_to_cache(row_data, cache)

  return cache


# 保存静态资源数据
def save_static_to_cache(record: dict, cache: dict) -> None:
  url = record.get('url', '')
  if not url:
    return
  search_key = create_md5(url)
  cache[search_key] = record


# 读取本地静态资源抓包数据到缓存
@error_catch(error_msg='读取本地静态资源抓包数据异常', error_return={})
def load_static_cache(path: str = '') -> dict:
  # 路径检查
  if not os.path.isfile(path):
    print('@@load_static_cache: 静态资源抓包数据文件不存在！ {}'.format(path))
    return {}

  data = pd.read_json(path)
  fieldnames = ["type", "url"]
  cache = {}
  # 行遍历
  for row_index, row_data in data.iterrows():
    record = {}
    for key in fieldnames:
      record[key] = row_data.get(key)
    save_static_to_cache(record, cache)

  return cache


# 保存抓包数据到本地
@error_catch(error_msg='保存抓包数据到本地异常')
def save_response(path: str, cache: dict) -> None:
  field_keys = [field.get('key') for field in MITMPROXY_DATA_FIELDS]
  data = {}
  for name in field_keys:
    data[name] = []

  for response_data in cache.values():
    for record in response_data.values():
      # 将数据存入对应列
      for key, value in record.items():
        if key in data:
          data[key].append(value)

  df = pd.DataFrame(data)
  # 将DataFrame写入Excel文件，每行为一个数据
  df.to_json(path, force_ascii=False, orient='records')


# 保存静态资源数据到本地
@error_catch(error_msg='保存抓包数据到本地异常')
def save_static(path: str, cache: dict) -> None:
  fieldnames = ["type", "url"]
  data = {}
  for name in fieldnames:
    data[name] = []

  for record in cache.values():
    # 将数据存入对应列
    for key, value in record.items():
      if key in data:
        data[key].append(value)

  df = pd.DataFrame(data)
  # 将DataFrame写入Excel文件，每行为一个数据
  df.to_json(path, force_ascii=False, orient='records')
