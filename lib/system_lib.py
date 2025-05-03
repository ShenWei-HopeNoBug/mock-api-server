from lib.utils_lib import ConfigFileManager
from config.work_file import SYSTEM_FILE_DICT

_GLOBALS_CONFIG: dict = SYSTEM_FILE_DICT.get('GLOBALS_CONFIG', {})
_HISTORY_CONFIG: dict = SYSTEM_FILE_DICT.get('HISTORY_CONFIG', {})

# 全局配置文件管理器
GLOBALS_CONFIG_MANAGER = ConfigFileManager(
  path=_GLOBALS_CONFIG.get('path'),
  config=_GLOBALS_CONFIG.get('default'),
)

# 历史记录配置文件管理器
HISTORY_CONFIG_MANAGER = ConfigFileManager(
  path=_HISTORY_CONFIG.get('path'),
  config=_HISTORY_CONFIG.get('default'),
)
