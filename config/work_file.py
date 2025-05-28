# -*- coding: utf-8 -*-


# -------------------------------------------------------------
# APP系统文件工作目录
SYSTEM_DIR = r'./system'

# 全局配置文件路径
GLOBALS_CONFIG_PATH = r'{}/globals.json'.format(SYSTEM_DIR)
# 历史记录问价路径
HISTORY_CONFIG_PATH = r'{}/history.json'.format(SYSTEM_DIR)

# -------------------------------------------------------------
# APP默认工作目录
DEFAULT_WORK_DIR = './server'

# 存放配置文件的目录
CONFIG_DIR = r'/config'
# 抓包配置文件路径
MITMPROXY_CONFIG_PATH = r'{}/mitmproxy_config.json'.format(CONFIG_DIR)
# mock服务配置文件路径
MOCK_SERVER_CONFIG_PATH = r'{}/mock_server_config.json'.format(CONFIG_DIR)

# 存放数据文件的目录
DATA_DIR = r'/data'
# 抓包数据文件路径
MITMPROXY_DATA_PATH = r'{}/output.json'.format(DATA_DIR)
# 用户自定义接口数据文件路径
USER_API_DATA_PATH = r'{}/user_api.json'.format(DATA_DIR)
# 静态资源数据文件路径
STATIC_DATA_PATH = r'{}/static.json'.format(DATA_DIR)
# 服务创建接口缓存文件地址
API_CACHE_DATA_PATH = r'{}/api_cache.json'.format(DATA_DIR)

# 静态资源目录
STATIC_DIR = r'/static'

# 下载目录
DOWNLOAD_DIR = r'/download'

# 导出目录
OUTPUT_DIR = r'/output'

# -------------------------------------------------------------
# 系统文件字典
SYSTEM_FILE_DICT = {
  "GLOBALS_CONFIG": {
    "path": GLOBALS_CONFIG_PATH,
    "default": {
      "client_exit": False,  # 是否已经退出程序
      "mitmproxy_stop_signal": False,  # 抓包停止信号
      "download_exit": False, # 是否已经退出下载
    }
  },
  "HISTORY_CONFIG": {
    "path": HISTORY_CONFIG_PATH,
    "default": {
      "work_dir": DEFAULT_WORK_DIR,  # app 工作目录
    }
  }
}

# 配置文件夹字典
WORK_DIR_DICT = {
  # 配置目录
  "CONFIG_DIR": {
    "path": CONFIG_DIR
  },
  # 数据目录
  "DATA_DIR": {
    "path": DATA_DIR
  },
  # 静态资源目录
  "STATIC_DIR": {
    "path": STATIC_DIR
  },
  # 下载目录
  "DOWNLOAD_DIR": {
    "path": DOWNLOAD_DIR
  },
  # 导出目录
  "OUTPUT_DIR": {
    "path": OUTPUT_DIR
  }
}

# 工作文件字典
WORK_FILE_DICT = {
  # ---------------------------------------------------
  # mitmproxy 抓包默认配置
  # include_path: 抓包链接要包含的文本内容
  # static_include_path: 抓包静态资源链接要包含的文本内容
  # ---------------------------------------------------
  "MITMPROXY_CONFIG": {
    "path": MITMPROXY_CONFIG_PATH,
    "default": {
      "include_path": "www.baidu.com",
      "static_include_path": []
    }
  },
  # ---------------------------------------------------
  # mock 服务的配置
  # include_files: 启动服务后要动态替换的静态资源链接扩展名列表
  # static_match_route: 动态匹配静态资源请求的路由
  # ---------------------------------------------------
  "MOCK_SERVER_CONFIG": {
    "path": MOCK_SERVER_CONFIG_PATH,
    "default": {
      "include_files": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
      "static_match_route": []
    }
  },
  "MITMPROXY_DATA": {
    "path": MITMPROXY_DATA_PATH,
    "default": [],
  },
  "USER_API_DATA": {
    "path": USER_API_DATA_PATH,
    "default": [],
  },
  "STATIC_DATA": {
    "path": STATIC_DATA_PATH,
    "default": [],
  },
  "API_CACHE_DATA": {
    "path": API_CACHE_DATA_PATH,
    "default": {},
  }
}
