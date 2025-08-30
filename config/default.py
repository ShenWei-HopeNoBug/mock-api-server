# -*- coding: utf-8 -*-
# ------------------------------
# 全局默认参数
# ------------------------------
from config.enum import SERVER

# 下载连接超时时间（s）
DEFAULT_DOWNLOAD_CONNECT_TIMEOUT = 120
# 下载时自动调整连接超时时间
DEFAULT_AUTO_ADJUST_DOWNLOAD_TIMEOUT = True
# Mock服务Params参数匹配模式
DEFAULT_HTTP_PARAMS_MATCH_MODE = SERVER.HTTP_PARAMS_EXACT_MATCH
