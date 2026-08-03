# -*- coding: utf-8 -*-
"""
GUI 相关的类型定义
"""
from enum import Enum
from typing import List, Literal, Optional, TypedDict

from app_types.db_types import ApiData


class RequestContentType(str, Enum):
  """
  请求 content-type 枚举值

  用于统一描述请求体的内容类型，特别是 POST 请求。
  """
  NONE = 'NONE'
  APPLICATION_X_WWW_FORM_URLENCODED = 'APPLICATION_X_WWW_FORM_URLENCODED'
  APPLICATION_JSON = 'APPLICATION_JSON'
  MULTIPART_FORM_DATA = 'MULTIPART_FORM_DATA'


class GetMockDataPageParams(TypedDict, total=False):
  """
  get_mock_data_page 请求参数（分页版）

  type 为数据来源类型过滤: 'USER' / 'MITMPROXY'，None 或不传表示全部（USER 在前）。
  url / params / response 为模糊查询关键词，不传表示不过滤。
  method 为精确查询('GET' / 'POST')，None 或不传表示全部。
  request_content_type 为精确查询，不传表示全部。
  """
  type: Optional[Literal['USER', 'MITMPROXY']]
  page_num: int  # 1-based 页码
  page_size: int  # 每页条数
  url: Optional[str]  # url 模糊查询关键词
  params: Optional[str]  # params 模糊查询关键词
  response: Optional[str]  # response 模糊查询关键词
  method: Optional[Literal['GET', 'POST']]
  request_content_type: Optional[RequestContentType]  # 请求 content-type 精确查询
  enabled: Optional[bool]  # 启用状态精确查询，True 启用，False 禁用，None 或不传表示全部
  create_start_time: Optional[str]  # 创建时间区间起点，格式 'YYYY-MM-DD HH:MM:SS'，需与 create_end_time 同时传
  create_end_time: Optional[str]  # 创建时间区间终点，格式 'YYYY-MM-DD HH:MM:SS'，需与 create_start_time 同时传


class MockDataPageResult(TypedDict):
  """
  get_mock_data_page 返回数据（分页版）

  list 为当前页的 API 记录列表，total 为符合条件的总记录数。
  """
  list: List[ApiData]  # 当前页数据
  total: int  # 符合条件的总记录数
  page_num: int  # 当前页码（1-based）
  page_size: int  # 每页条数


class DeleteMockDataParams(TypedDict):
  """
  delete_mock_data 请求参数
  """
  id: str  # 待删除记录的 id


class BatchDeleteMockDataParams(TypedDict, total=False):
  """
  batch_delete_mock_data 请求参数

  筛选条件与 get_mock_data_page 完全一致，支持按当前表格筛选条件批量删除。
  type 为数据来源类型过滤: 'USER' / 'MITMPROXY'，不传表示不按类型过滤。
  url / params / response 为模糊查询关键词，不传表示不过滤。
  method 为精确查询('GET' / 'POST')，不传表示全部。
  request_content_type 为精确查询，不传表示全部。
  create_start_time / create_end_time 为创建时间区间，必须成对传入才生效。
  至少提供任一筛选条件，否则后端拒绝执行（防止全表删除）。
  """
  type: Optional[Literal['USER', 'MITMPROXY']]
  url: Optional[str]  # url 模糊查询关键词
  params: Optional[str]  # params 模糊查询关键词
  response: Optional[str]  # response 模糊查询关键词
  method: Optional[Literal['GET', 'POST']]
  request_content_type: Optional[RequestContentType]  # 请求 content-type 精确查询
  enabled: Optional[bool]  # 启用状态精确查询，True 启用，False 禁用，None 或不传表示全部
  create_start_time: Optional[str]
  create_end_time: Optional[str]


class AddMockDataParams(TypedDict, total=False):
  """
  add_mock_data 请求参数

  type 由 handler 硬编码为 'USER'，id 由 MockDB.insert_api 内部生成，均不需要前端传入。
  """
  url: str  # 请求 URL
  method: str  # HTTP 方法
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串


class CopyMockDataParams(TypedDict):
  """
  copy_mock_data 请求参数

  只需传源记录的 id，handler 按 id 查库取完整数据后复制插入。
  """
  id: str  # 待复制的源记录 id


class AppServerRunningData(TypedDict):
  """
  APP_SERVER 启动结果数据

  用于 start_app_server 的返回值，以及 MainWindow / Dialog 中
  app_sever_running_data 的传递类型。
  """
  success: bool  # APP_SERVER 是否成功启动
  port: int  # APP_SERVER 监听端口号
