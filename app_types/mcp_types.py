# -*- coding: utf-8 -*-
"""
MCP 工具返回值类型

DB 层 OperationResult 已于 v0_1_5 移除冗余的 success 字段
（status_code 为成败唯一权威）；但 MCP 工具面向 LLM 客户端，
布尔 success 更易读，故在 MCP 边界由 status_code 派生补齐，
对外契约保持不变：success = (status_code == BIZ_SUCCESS)。
"""
from typing import Optional, TypedDict, Union


class McpOperationResult(TypedDict):
  """
  MCP 工具操作结果

  success 由 status_code == 0 派生，仅存在于 MCP 边界，不回写 DB 层。
  """
  success: bool     # 操作是否成功（= status_code == 0）
  status_code: int  # 状态码：0 表示成功，非 0 表示失败（使用 BIZ_CODE）
  status_msg: str   # 操作结果消息


class McpOperationResultWithOptionalId(McpOperationResult, total=False):
  """带可选记录 ID 的 MCP 操作结果"""
  id: Optional[str]


class McpBatchOperationResult(McpOperationResult):
  """批量操作结果"""
  affected_count: int  # 影响的记录数


# 统一的 MCP 操作结果类型别名
McpDbOperationResult = Union[McpOperationResult, McpOperationResultWithOptionalId, McpBatchOperationResult]
