import os
import shutil
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
import logging


class SimpleFolderBackup:
  """
  简单文件夹备份工具类

  使用 shutil.copytree 实现文件夹备份功能
  """

  def __init__(self, source_dir: str, backup_dir: str):
    """
    初始化备份工具

    Args:
        source_dir: 需要备份的源文件夹路径
        backup_dir: 备份文件存放的目标文件夹路径
    """
    self.source_dir = source_dir
    self.backup_dir = backup_dir
    self._ensure_directory_exists(self.backup_dir)
    self.logger = self._setup_logger()

  def _setup_logger(self) -> logging.Logger:
    """设置日志记录器"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

  def _ensure_directory_exists(self, directory: str) -> None:
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(directory):
      os.makedirs(directory, exist_ok=True)
      self.logger.info(f"创建目录: {directory}")

  def _get_backup_path(self, prefix: str = "backup") -> str:
    """生成带时间戳的备份文件夹路径"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{prefix}_{timestamp}"
    return os.path.join(self.backup_dir, backup_name)

  def backup(self, backup_name: Optional[str] = None) -> Tuple[bool, str]:
    """
    执行备份操作

    Args:
        backup_name: 自定义备份文件夹名称（可选）

    Returns:
        Tuple[bool, str]: (是否成功, 备份路径或错误信息)
    """
    if not os.path.exists(self.source_dir):
      error_msg = f"源文件夹不存在: {self.source_dir}"
      self.logger.error(error_msg)
      return False, error_msg

    try:
      # 获取备份路径
      backup_path = self._get_backup_path(backup_name) if backup_name else self._get_backup_path()

      # 如果目标文件夹已存在，添加数字后缀
      counter = 1
      original_backup_path = backup_path
      while os.path.exists(backup_path):
        backup_path = f"{original_backup_path}_{counter}"
        counter += 1

      self.logger.info(f"开始备份: {self.source_dir} -> {backup_path}")

      # 使用 copytree 复制整个目录树
      shutil.copytree(
        self.source_dir,
        backup_path,
        dirs_exist_ok=True,  # 如果目标目录已存在则合并
        copy_function=shutil.copy2  # 保留文件元数据
      )

      self.logger.info(f"备份成功: {backup_path}")
      return True, backup_path

    except Exception as e:
      error_msg = f"备份过程中发生错误: {str(e)}"
      self.logger.error(error_msg, exc_info=True)
      return False, error_msg

  def list_backups(self) -> List[Dict[str, Any]]:
    """列出所有备份"""
    if not os.path.exists(self.backup_dir):
      return []

    backups = []
    for item in os.listdir(self.backup_dir):
      item_path = os.path.join(self.backup_dir, item)
      if os.path.isdir(item_path):
        try:
          mtime = os.path.getmtime(item_path)
          size = sum(
            os.path.getsize(os.path.join(dirpath, filename))
            for dirpath, _, filenames in os.walk(item_path)
            for filename in filenames
          )
          backups.append({
            'name': item,
            'path': item_path,
            'size': size,
            'date': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
          })
        except Exception as e:
          self.logger.warning(f"获取备份信息失败 {item_path}: {str(e)}")

    # 按修改时间降序排序
    backups.sort(key=lambda x: x['date'], reverse=True)
    return backups


# 使用示例
if __name__ == "__main__":
  # 配置日志
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
  )

  # 创建备份实例
  backup = SimpleFolderBackup(
    source_dir=r"B:\project\pycharm\mock-api-server\server\data",  # 替换为你要备份的文件夹
    backup_dir=r"B:\project\pycharm\mock-api-server\server\backup"  # 替换为备份存放的目录
  )

  # 执行备份
  success, result = backup.backup()
  if success:
    print(f"备份成功！备份位置: {result}")
  else:
    print(f"备份失败: {result}")

  # 查看所有备份
  print("\n所有备份:")
  for idx, item in enumerate(backup.list_backups(), 1):
    print(f"{idx}. {item['name']} - {item['date']} - {item['size'] / 1024 / 1024:.2f} MB")
