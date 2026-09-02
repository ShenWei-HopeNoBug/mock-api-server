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
  /mock_data/list 请求参数（分页版）

  type 为数据来源类型过滤: 'USER' / 'MITMPROXY' / 'MCP'，None 或不传表示全部（USER 在前）。
  url / params / response 为模糊查询关键词，不传表示不过滤。
  method 为精确查询('GET' / 'POST')，None 或不传表示全部。
  request_content_type 为精确查询，不传表示全部。
  """
  type: Optional[Literal['USER', 'MITMPROXY', 'MCP']]
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
  operator: Optional[str]  # 操作来源精确匹配，如 'USER' / 'MCP'，不传表示全部


class MockDataPageResult(TypedDict):
  """
  /mock_data/list 返回数据（分页版）

  list 为当前页的 API 记录列表，total 为符合条件的总记录数。
  """
  list: List[ApiData]  # 当前页数据
  total: int  # 符合条件的总记录数
  page_num: int  # 当前页码（1-based）
  page_size: int  # 每页条数


class DeleteMockDataParams(TypedDict):
  """
  /mock_data/delete 请求参数
  """
  id: str  # 待删除记录的 id


class BatchDeleteMockDataParams(TypedDict, total=False):
  """
  /mock_data/batch_delete 请求参数

  筛选条件与 /mock_data/list 完全一致，支持按当前表格筛选条件批量删除。
  type 为数据来源类型过滤: 'USER' / 'MITMPROXY' / 'MCP'，不传表示不按类型过滤。
  url / params / response 为模糊查询关键词，不传表示不过滤。
  method 为精确查询('GET' / 'POST')，不传表示全部。
  request_content_type 为精确查询，不传表示全部。
  create_start_time / create_end_time 为创建时间区间，必须成对传入才生效。
  至少提供任一筛选条件，否则后端拒绝执行（防止全表删除）。
  """
  type: Optional[Literal['USER', 'MITMPROXY', 'MCP']]
  url: Optional[str]  # url 模糊查询关键词
  params: Optional[str]  # params 模糊查询关键词
  response: Optional[str]  # response 模糊查询关键词
  method: Optional[Literal['GET', 'POST']]
  request_content_type: Optional[RequestContentType]  # 请求 content-type 精确查询
  enabled: Optional[bool]  # 启用状态精确查询，True 启用，False 禁用，None 或不传表示全部
  create_start_time: Optional[str]
  create_end_time: Optional[str]
  operator: Optional[str]  # 操作来源精确匹配，如 'USER' / 'MCP'，不传表示不筛选


class AddMockDataParams(TypedDict, total=False):
  """
  /mock_data/create 请求参数

  type 由 handler 硬编码为 'USER'，id 由 MockDB.insert_api 内部生成，均不需要前端传入。
  """
  url: str  # 请求 URL
  method: str  # HTTP 方法，仅支持 'GET' / 'POST'
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串


class CopyMockDataParams(TypedDict):
  """
  /mock_data/copy 请求参数

  只需传源记录的 id，handler 按 id 查库取完整数据后复制插入。
  """
  id: str  # 待复制的源记录 id


class GetMockDataDetailParams(TypedDict):
  """
  /mock_data/detail 请求参数

  只需传记录 id，handler 按 id 查库返回完整详情（含变体列表）。
  """
  id: str  # 待查询记录的 id


class AddVariantParams(TypedDict, total=False):
  """
  /variant/create 请求参数

  用于创建并绑定 response 变体到指定 api_data。
  id 由 MockDB.insert_variant 内部生成，不需要前端传入。
  """
  api_data_id: str  # 所属 api_data 的 ID
  name: str  # 变体名称
  response: str  # 变体响应体，JSON 字符串
  enabled: bool  # 是否启用（True 启用，False 禁用），缺省时默认启用
  timeout: int  # idle 回退超时时间（毫秒），0 表示不启用


class UpdateVariantParams(TypedDict, total=False):
  """
  /variant/update 请求参数

  用于更新指定 response 变体，字段级合并，id 为必需。
  api_data_id 不允许通过此接口修改。
  """
  id: str  # 待更新变体的 ID
  name: str  # 变体名称
  response: str  # 变体响应体，JSON 字符串
  enabled: bool  # 是否启用（True 启用，False 禁用）
  timeout: int  # idle 回退超时时间（毫秒），0 表示不启用


class DeleteVariantParams(TypedDict):
  """
  /variant/delete 请求参数
  """
  id: str  # 待删除变体的 ID


class ReorderVariantParams(TypedDict):
  """
  /variant/reorder 请求参数

  用于重新排序 api_data 绑定的 response_variant_ids。
  variant_ids 必须与当前绑定的 id 列表元素完全一致（仅顺序不同），否则后端拒绝。
  """
  api_data_id: str  # 所属 api_data 的 ID
  variant_ids: List[str]  # 重新排序后的变体 ID 列表


class CopyVariantParams(TypedDict):
  """
  /variant/copy 请求参数

  传入源变体 id 和目标 api_data_id，handler 按 id 查库取源变体数据，
  复制后绑定到指定的 api_data 上。新变体默认不启用。
  """
  id: str            # 源变体 ID
  api_data_id: str   # 目标 api_data ID


class SetVariantExclusiveEnabledParams(TypedDict):
  """
  /variant/set_exclusive_enabled 请求参数

  传入目标变体 id，handler 将该变体设为启用，同时禁用同一 api_data_id 下的所有其他变体。
  """
  id: str  # 目标变体 ID


class AppServerRunningData(TypedDict):
  """
  APP_SERVER 启动结果数据

  用于 start_app_server 的返回值，以及 MainWindow / Dialog 中
  app_sever_running_data 的传递类型。
  """
  success: bool  # APP_SERVER 是否成功启动
  port: int  # APP_SERVER 监听端口号
