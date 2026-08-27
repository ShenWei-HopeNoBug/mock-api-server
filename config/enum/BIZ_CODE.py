# -*- coding: utf-8 -*-

# ---------------------------------------------------
# Qt Bridge 业务状态码
# 编码规则：5 位负数，前两位标识错误大类，后三位标识具体错误
# 0 = 成功，非 0 = 失败
# ---------------------------------------------------

# 成功
BIZ_SUCCESS: int = 0

# --- 通用/系统错误 -10xxx ---
BIZ_UNKNOWN_ERROR: int = -10001        # 未知异常
BIZ_INTERNAL_ERROR: int = -10002       # 内部错误

# --- 参数校验错误 -20xxx ---
BIZ_PARAM_MISSING: int = -20001        # 必填参数缺失
BIZ_PARAM_INVALID: int = -20002        # 参数格式非法
BIZ_DATA_EMPTY: int = -20003           # 数据为空

# --- 数据操作错误 -30xxx ---
BIZ_DATA_NOT_FOUND: int = -30001       # 数据不存在
BIZ_DATA_ALREADY_EXISTS: int = -30002  # 数据已存在
BIZ_DB_ERROR: int = -30003             # 数据库读写异常
BIZ_CONSTRAINT_VIOLATION: int = -30004 # 约束违反

# --- 文件/IO 错误 -40xxx ---
BIZ_FILE_READ_ERROR: int = -40001      # 文件读取失败
BIZ_FILE_WRITE_ERROR: int = -40002     # 文件写入失败
