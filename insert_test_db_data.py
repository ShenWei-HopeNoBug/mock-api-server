# -*- coding: utf-8 -*-

import sys
import os
from lib.db_lib import MockDBCache
from typing import List
from app_types.db_types import ApiRecord

test_api_records: List[ApiRecord] = [
  # GET 无参数 —— 用户列表
  {
    'type': 'USER',
    'url': 'https://api.example.com/users',
    'method': 'GET',
    'params': '{}',
    'response': '{"code":0,"msg":"success","data":[{"id":1,"name":"Alice","age":25},{"id":2,"name":"Bob","age":30}]}',
    'timeout': 0,
  },
  # GET 带 query 参数 —— 分页查询
  {
    'type': 'USER',
    'url': 'https://api.example.com/users?page=1&size=10',
    'method': 'GET',
    'params': '{"page":"1","size":"10"}',
    'response': '{"code":0,"msg":"success","data":{"list":[{"id":1,"name":"Alice"},{"id":2,"name":"Bob"}],"total":2,"page":1,"size":10}}',
    'timeout': 0,
  },
  # POST JSON body —— 创建用户
  {
    'type': 'USER',
    'url': 'https://api.example.com/users',
    'method': 'POST',
    'params': '{"name":"Charlie","age":28}',
    'response': '{"code":0,"msg":"创建成功","data":{"id":3,"name":"Charlie","age":28}}',
    'timeout': 0,
  },
  # POST 表单提交 —— 登录
  {
    'type': 'USER',
    'url': 'https://api.example.com/login',
    'method': 'POST',
    'params': '{"username":"admin","password":"123456"}',
    'response': '{"code":0,"msg":"登录成功","data":{"token":"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.fake-token","expire":3600}}',
    'timeout': 0,
  },
  # 带自定义超时 —— 模拟慢接口
  {
    'type': 'USER',
    'url': 'https://api.example.com/slow-api',
    'method': 'GET',
    'params': '{}',
    'response': '{"code":0,"msg":"success","data":"this is a slow response"}',
    'timeout': 2000,
  },
]


def main():
  db_path = './server'
  mock_db = MockDBCache.get(work_dir=db_path)
  success = mock_db.batch_insert_api(test_api_records)
  print(f'测试数据插入 {"成功" if success else "失败"}，共 {len(test_api_records)} 条')
  MockDBCache.close_all()


if __name__ == '__main__':
  main()
  sys.exit(0)
