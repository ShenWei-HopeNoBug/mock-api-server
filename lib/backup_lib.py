# -*- coding: utf-8 -*-
import os
import shutil
from datetime import datetime
from typing import List, Dict, Any
from lib.logger_lib import STREAM_LOGGER
from lib.decorate import error_catch
from logging import Logger
import re
import sys


class SimpleFolderBackup:
  """简单文件夹备份工具类"""

  def __init__(self, source_dir: str, backup_dir: str, prefix: str = "backup", backup_count: int = 50) -> None:
    """
    初始化备份工具

    Args:
        source_dir: 需要备份的源文件夹路径
        backup_dir: 备份文件存放的目标文件夹路径
        prefix: 备份文件夹前缀
        backup_count: 备份文件夹数量限制（传0为无上限）
    """
    self.source_dir: str = os.path.abspath(source_dir)
    self.backup_dir: str = os.path.abspath(backup_dir)
    self.backup_count: int = backup_count
    self.prefix: str = prefix
    self.logger: Logger = STREAM_LOGGER
    self.source_dir_name: str = ''

    self.init()

  def init(self):
    self._ensure_directory_exists(self.backup_dir)
    # 记录源文件的文件名
    if self._check_dir_valid(self.source_dir):
      self.source_dir_name = os.path.basename(self.source_dir)

  @error_catch(error_msg='备份文件异常', error_return=False)
  def backup(self) -> bool:
    """
    执行备份操作
    """
    if not self._check_dir_valid(self.source_dir):
      self.logger.error(f"源文件夹路径非法: {self.source_dir}")
      return False

    # 获取备份路径
    backup_path = self._get_backup_path()

    # 如果目标文件夹已存在，不进行备份
    if os.path.exists(backup_path):
      self.logger.error(f"备份到的目标文件夹已存在：{backup_path}")
      return False

    self.logger.info(f"开始备份: {self.source_dir} -> {backup_path}")

    # 使用 copytree 复制整个目录树
    shutil.copytree(
      src=self.source_dir,
      dst=backup_path,
    )

    self.logger.info(f"备份成功: {backup_path}")
    # 备份成功后检查并删除超出备份数量上限的文件
    self.fix_backup_dir_count()
    return True

  @error_catch(error_msg='列出所有备份异常', error_return=[])
  def list_backups(self) -> List[Dict[str, Any]]:
    """列出所有备份"""

    if not self._check_dir_valid(self.backup_dir):
      self.logger.error(f"备份文件夹路径非法: {self.backup_dir}")
      return []

    backups = []
    for dir_name in os.listdir(self.backup_dir):
      back_up_path = os.path.abspath(f"{self.backup_dir}/{dir_name}")
      # 跳过非文件夹类型路径以及非标准命名的文件夹
      if not self._check_backup_path_valid(back_up_path):
        continue

      try:
        timestamp = self._get_backup_path_timestamp(back_up_path)
        sort_time = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        if not timestamp:
          continue

        backups.append({
          'name': dir_name,
          'path': back_up_path,
          'timestamp': timestamp,
          'sort_time': sort_time
        })
      except Exception as e:
        self.logger.warning(f"获取备份信息失败 {back_up_path}: {str(e)}")

    # 按时间戳降序排序
    backups.sort(key=lambda x: x['sort_time'], reverse=True)

    # 返回数据去除排序时间戳数据
    result_list = [
      {
        "name": backup_data.get('name'),
        "path": backup_data.get('path'),
        "timestamp": backup_data.get('timestamp'),
      } for backup_data in backups
    ]

    return result_list

  @error_catch(error_msg='将备份文件夹恢复到指定目录异常', error_return=False)
  def restore(self, backup_path: str) -> bool:
    """
    将备份恢复到指定目录（默认恢复到源目录）
    """

    # 确定目标目录
    restore_to = self.source_dir
    self.logger.info(f"准备从 {backup_path} 恢复到 {restore_to}")

    # 检查备份目录是否存在
    if not self._check_backup_path_valid(backup_path):
      self.logger.error(f"恢复文件时备份目录路径不合法: {backup_path}")
      return False

    # 如果目标目录已存在，先删除它
    if os.path.exists(restore_to):
      self.logger.info(f"目标目录已存在，正在删除: {restore_to}")
      shutil.rmtree(restore_to)

    # 确保目标目录的父目录存在
    os.makedirs(os.path.basename(restore_to), exist_ok=True)

    # 复制备份到目标目录
    self.logger.info(f"正在恢复备份: {backup_path} -> {restore_to}")
    shutil.copytree(src=backup_path, dst=restore_to)

    success_msg = f"恢复成功: {backup_path} -> {restore_to}"
    self.logger.info(success_msg)
    return True

  def restore_latest(self) -> bool:
    """
    将最新的备份恢复到源目录
    """

    # 获取最近一次备份文件夹地址
    latest_backup_path = self.get_latest_backup_path()
    if latest_backup_path:
      self.logger.info(f"找到最新的备份: {latest_backup_path}")
      return self.restore(latest_backup_path)
    else:
      self.logger.error(f"未找到最新的备份")
      return False

  def get_latest_backup_path(self) -> str:
    """找到最新的备份文件夹路径"""
    backup_data_list = self.list_backups()
    if not len(backup_data_list):
      return ''

    latest_data = backup_data_list[0]
    return latest_data.get('path', '')

  @error_catch(error_msg='检查并删除超出备份数量的备份文件异常')
  def fix_backup_dir_count(self):
    """检查并删除超出备份数量的备份文件"""
    if not self.backup_count:
      return

    backup_data_list = self.list_backups()
    backup_length = len(backup_data_list)
    if backup_length <= self.backup_count:
      return

    delete_backup_data_list = backup_data_list[(self.backup_count - backup_length):]
    delete_dir_list = [backup_data.get('path') for backup_data in delete_backup_data_list]
    # 删除超出备份上限数量的备份文件夹
    for delete_dir in delete_dir_list:
      if self._check_dir_valid(delete_dir):
        shutil.rmtree(delete_dir)

  @staticmethod
  def _check_dir_valid(dir_path: str) -> bool:
    """检查文件夹地址是否合法"""
    if type(dir_path) != str:
      return False

    # 地址存在并且是文件夹的地址
    return os.path.exists(dir_path) and os.path.isdir(dir_path)

  def _get_backup_path_timestamp(self, backup_path: str) -> str:
    if not self._check_backup_path_valid(backup_path):
      return ''

    backup_dir_name: str = os.path.basename(backup_path)
    last_underscore = backup_dir_name.rfind('_')
    timestamp_str = backup_dir_name[last_underscore + 1:]
    return timestamp_str

  def _ensure_directory_exists(self, directory: str) -> None:
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(directory):
      os.makedirs(directory, exist_ok=True)
      self.logger.info(f"创建目录: {directory}")

  def _get_backup_path(self) -> str:
    """生成带时间戳的备份文件夹路径"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_name = f"{self.prefix}_{self.source_dir_name}_{timestamp}"
    backup_path = f"{self.backup_dir}/{backup_name}"
    return os.path.abspath(backup_path)

  @error_catch(error_msg='检查备份文件路径异常', error_return=False)
  def _check_backup_path_valid(self, backup_path: str) -> bool:
    if not self._check_dir_valid(backup_path):
      return False

    backup_dir_name: str = os.path.basename(backup_path)
    # 以特定前缀开头，并以 14 位数字结尾
    pattern: str = r'^' + self.prefix + r'_.*_\d{14}$'
    return bool(re.match(pattern, backup_dir_name))


def test():
  # 创建备份实例
  simple_folder_back_up = SimpleFolderBackup(
    source_dir=r"B:\project\pycharm\mock-api-server\server\data",
    backup_dir=r"B:\project\pycharm\mock-api-server\server\backup\data",
    backup_count=3
  )

  # 备份文件测试
  simple_folder_back_up.backup()

  # 恢复最新备份测试
  # simple_folder_back_up.restore_latest()

  # 检查并删除超出备份数量的备份文件
  # simple_folder_back_up.fix_backup_dir_count()

  # 列出备份列表测试
  backups = simple_folder_back_up.list_backups()
  for index, backup in enumerate(backups):
    name = backup.get('name', '')
    path = backup.get('path', '')
    timestamp = backup.get('timestamp', '')
    print(f"backup-{index + 1}\n文件名：{name}\n文件地址：{path}\ntimestamp：{timestamp}\n")


# 使用示例
if __name__ == "__main__":
  test()
  sys.exit(0)
