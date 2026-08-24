# -*- coding: utf-8 -*-
"""
数据库相关的类型定义
"""
from typing import List, Optional, TypedDict, Union


class ApiRecord(TypedDict, total=False):
  """
  API 数据写入参数

  用于 insert_api / update_api / batch_insert_api 的入参。
  total=False 表示所有字段可选，调用方按需传入。
  """
  id: str  # 记录唯一标识（upsert 时由代码生成，batch 时由外部传入）
  type: str  # 数据来源类型，如 'MITMPROXY' / 'USER' / 'MCP'
  url: str  # 请求 URL
  method: str  # HTTP 方法，如 'GET' / 'POST'
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串
  response_variant_ids: List[str]  # 绑定的 response 变体 ID 列表，缺省为 []
  enabled: bool  # 是否启用（True 启用，False 禁用），缺省时默认启用
  timeout: int  # 超时时间（毫秒），0 表示不限制
  request_content_type: str  # 请求 content-type 枚举值


class ApiData(TypedDict):
  """
  API 数据完整记录

  用于 get_api_list 的返回值，包含数据库中的全部字段。
  """
  id: str  # 记录唯一标识
  type: str  # 数据来源类型
  url: str  # 请求 URL
  method: str  # HTTP 方法
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串
  response_variant_ids: List[str]  # 绑定的 response 变体 ID 列表
  enabled: bool  # 是否启用（True 启用，False 禁用）
  timeout: int  # 超时时间（毫秒），0 表示不限制
  request_content_type: str  # 请求 content-type 枚举值
  created_at: str  # 创建时间，格式 'YYYY-MM-DD HH:MM:SS.sss'
  updated_at: str  # 更新时间，格式 'YYYY-MM-DD HH:MM:SS.sss'


class ApiQuery(TypedDict, total=False):
  """
  API 数据查询过滤参数

  用于 get_api_list / get_api_list_page / get_api_count 的入参。
  total=False 表示所有字段可选，调用方按需传入。
  """
  api_type: Optional[str]  # 数据来源类型精确匹配，如 'USER' / 'MITMPROXY' / 'MCP'
  url_like: Optional[str]  # URL 模糊查询
  params_like: Optional[str]  # 请求参数模糊查询
  response_like: Optional[str]  # 响应体模糊查询
  method: Optional[str]  # HTTP 方法精确查询
  request_content_type: Optional[str]  # 请求 content-type 枚举值精确查询
  enabled: Optional[bool]  # 是否启用，True 启用，False 禁用，None 不筛选
  create_start_time: Optional[str]  # 创建时间区间起点，格式 'YYYY-MM-DD HH:MM:SS.sss'
  create_end_time: Optional[str]  # 创建时间区间终点，格式 'YYYY-MM-DD HH:MM:SS.sss'


class ApiResponseVariantInsertRecord(TypedDict, total=False):
  """
  API response 变体新增参数

  用于 insert_variant 的入参。id 由服务端生成，调用方不需要传入。
  total=False 表示所有字段可选，调用方按需传入。
  """
  api_data_id: str  # 所属 api_data 的 ID
  name: str  # 变体名称
  response: str  # 变体响应体，JSON 字符串
  enabled: bool  # 是否启用（True 启用，False 禁用），缺省时默认启用
  timeout: int  # idle 回退超时时间（毫秒），0 表示不启用


class ApiResponseVariantRecord(TypedDict, total=False):
  """
  API response 变体更新参数

  用于 update_variant 的入参。
  total=False 表示所有字段可选，调用方按需传入。
  """
  id: str  # 记录唯一标识（update 时必需）
  api_data_id: str  # 所属 api_data 的 ID（不允许修改）
  name: str  # 变体名称
  response: str  # 变体响应体，JSON 字符串
  enabled: bool  # 是否启用（True 启用，False 禁用）
  timeout: int  # idle 回退超时时间（毫秒），0 表示不启用


class ApiResponseVariant(TypedDict):
  """
  API response 变体完整记录

  用于 get_variants_by_api_id 等查询的返回值。
  """
  id: str  # 记录唯一标识
  api_data_id: str  # 所属 api_data 的 ID
  name: str  # 变体名称
  response: str  # 变体响应体，JSON 字符串
  enabled: bool  # 是否启用（True 启用，False 禁用）
  timeout: int  # idle 回退超时时间（毫秒），0 表示不启用
  created_at: str  # 创建时间，格式 'YYYY-MM-DD HH:MM:SS.sss'
  updated_at: str  # 更新时间，格式 'YYYY-MM-DD HH:MM:SS.sss'


class ApiDataDetail(TypedDict):
  """
  API 数据详情（含变体列表）

  用于 get_api_detail 的返回值，在 ApiData 基础上关联查询 response 变体列表。
  """
  id: str  # 记录唯一标识
  type: str  # 数据来源类型
  url: str  # 请求 URL
  method: str  # HTTP 方法
  params: str  # 请求参数，JSON 字符串
  response: str  # 响应体，JSON 字符串
  response_variant_ids: List[str]  # 绑定的 response 变体 ID 列表
  response_variants: List[ApiResponseVariant]  # 关联查询的变体列表
  enabled: bool  # 是否启用（True 启用，False 禁用）
  timeout: int  # 超时时间（毫秒），0 表示不限制
  request_content_type: str  # 请求 content-type 枚举值
  created_at: str  # 创建时间，格式 'YYYY-MM-DD HH:MM:SS.sss'
  updated_at: str  # 更新时间，格式 'YYYY-MM-DD HH:MM:SS.sss'


class StaticData(TypedDict):
  """
  静态资源数据记录

  用于 get_static_list 的返回值。
  """
  id: str  # 记录唯一标识
  url: str  # 静态资源 URL
  type: str  # 数据来源类型
  created_at: str  # 创建时间
  updated_at: str  # 更新时间


class OperationResult(TypedDict):
  """
  数据库操作结果基础类型

  用于统一返回操作是否成功的状态及消息。
  """
  success: bool
  status_code: int  # 状态码：0 表示成功，非 0 表示失败（使用 BIZ_CODE）
  status_msg: str   # 操作结果消息：成功时返回 "成功"，失败时返回具体错误信息


class OperationResultWithId(TypedDict):
  """
  带记录 ID 的数据库操作结果

  用于需要返回新创建/操作记录 ID 的操作，如 insert、copy 等。
  """
  success: bool
  id: str
  status_code: int  # 状态码：0 表示成功，非 0 表示失败
  status_msg: str   # 操作结果消息


class OperationResultWithOptionalId(TypedDict, total=False):
  """
  带可选记录 ID 的数据库操作结果

  用于操作成功时可能返回记录 ID，失败时不返回 ID 的操作。
  """
  success: bool
  id: Optional[str]
  status_code: int  # 状态码：0 表示成功，非 0 表示失败
  status_msg: str   # 操作结果消息


class BatchOperationResult(TypedDict):
  """
  批量操作结果类型

  用于批量插入、批量删除等操作，返回操作成功状态及影响记录数等信息。
  """
  success: bool
  status_code: int  # 状态码：0 表示成功，非 0 表示失败
  status_msg: str   # 操作结果消息
  affected_count: int  # 影响的记录数


# 统一的操作结果类型别名
DbOperationResult = Union[OperationResult, OperationResultWithId, OperationResultWithOptionalId, BatchOperationResult]
