from lib.utils_lib import ConfigFileManager
from config.work_file import SYSTEM_FILE_DICT
import copy

_HISTORY_CONFIG: dict = SYSTEM_FILE_DICT.get('HISTORY_CONFIG', {})

# 历史记录配置文件管理器
HISTORY_CONFIG_MANAGER = ConfigFileManager(
  path=_HISTORY_CONFIG.get('path'),
  config=copy.deepcopy(_HISTORY_CONFIG.get('default')),
)
