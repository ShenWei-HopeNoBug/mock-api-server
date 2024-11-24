import hashlib
from urllib.parse import urlparse
import json

from conda.common.serialize import json_load


# 获取字符串的 md5
def create_md5(string = ''):
  return hashlib.md5(str(string).encode('utf-8')).hexdigest()

# 去掉链接里面的域名
def remove_url_domain(url = ''):
  parse_data = urlparse(url)
  return parse_data.path

# 格式化 json string 数据(业务映射)
def format_json_string(json_string):
  return json.dumps(json.loads(json_string), ensure_ascii=False)

# 格式化 dict 数据(业务映射)
def format_dict(dict_data):
  return json.loads(json.dumps(dict_data, ensure_ascii=False))

# 将字典转化成标准的 json string 数据(业务映射)
def format_dict_to_json_string(dict_data):
  return json.dumps(dict_data, ensure_ascii=False)
