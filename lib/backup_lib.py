# -*- coding: utf-8 -*-
import os
import shutil
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from lib.logger_lib import STREAM_LOGGER
import logging


class SimpleFolderBackup:
  """
  简单文件夹备份工具类

  使用 shutil.copytree 实现文件夹备份功能
  """

  def __init__(self, source_dir: str, backup_dir: str, prefix: str = "backup", backup_count=50) -> None:
    """
    初始化备份工具

    Args:
        source_dir: 需要备份的源文件夹路径
        backup_dir: 备份文件存放的目标文件夹路径
        prefix: 备份文件夹前缀
        backup_count: 备份文件夹数量限制
    """
    self.source_dir = source_dir
    self.backup_dir = backup_dir
    self.backup_count = backup_count
    self.prefix = prefix
    self.logger = STREAM_LOGGER
    self._ensure_directory_exists(self.backup_dir)

  def _ensure_directory_exists(self, directory: str) -> None:
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(directory):
      os.makedirs(directory, exist_ok=True)
      self.logger.info(f"创建目录: {directory}")

  def _get_backup_path(self) -> str:
    """生成带时间戳的备份文件夹路径"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_name = f"{self.prefix}_{timestamp}"
    backup_path = f"{self.backup_dir}/{backup_name}"
    return os.path.abspath(backup_path)

  def backup(self) -> bool:
    """
    执行备份操作
    """
    if not os.path.exists(self.source_dir):
      error_msg = f"源文件夹不存在: {self.source_dir}"
      self.logger.error(error_msg)
      return False

    try:
      # 获取备份路径
      backup_path = self._get_backup_path()

      # 如果目标文件夹已存在，添加数字后缀
      counter = 1
      original_backup_path = backup_path
      while os.path.exists(backup_path):
        backup_path = f"{original_backup_path}_{counter}"
        counter += 1

      self.logger.info(f"开始备份: {self.source_dir} -> {backup_path}")

      # 使用 copytree 复制整个目录树
      shutil.copytree(
        src=self.source_dir,
        dst=backup_path,
        dirs_exist_ok=True,  # 如果目标目录已存在则合并
        copy_function=shutil.copy2  # 保留文件元数据
      )

      self.logger.info(f"备份成功: {backup_path}")
      return True

    except Exception as e:
      error_msg = f"备份过程中发生错误: {str(e)}"
      self.logger.error(error_msg, exc_info=True)
      return False

  def list_backups(self) -> List[Dict[str, Any]]:
    """列出所有备份"""
    if not os.path.exists(self.backup_dir):
      return []

    backups = []
    for dir_name in os.listdir(self.backup_dir):
      dir_path = os.path.abspath(f"{self.backup_dir}/{dir_name}")
      # 跳过非文件夹类型路径以及非标准命名的文件夹
      if not os.path.isdir(dir_path) or not dir_name.startswith(f"{self.prefix}_"):
        continue

      try:
        mtime = os.path.getmtime(dir_path)

        backups.append({
          'name': dir_name,
          'path': dir_path,
          'date': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        })
      except Exception as e:
        self.logger.warning(f"获取备份信息失败 {dir_path}: {str(e)}")

    # 按修改时间降序排序
    backups.sort(key=lambda x: x['date'], reverse=True)
    return backups

  def restore(self, backup_path: str, target_dir: Optional[str] = None) -> Tuple[bool, str]:
    """
    将备份恢复到指定目录（默认恢复到源目录）

    Args:
        backup_path: 备份文件夹路径
        target_dir: 要恢复到的目标目录，如果为None则恢复到源目录

    Returns:
        Tuple[bool, str]: (是否成功, 成功信息或错误信息)
    """
    try:
      # 确定目标目录
      restore_to = target_dir if target_dir is not None else self.source_dir
      self.logger.info(f"准备从 {backup_path} 恢复到 {restore_to}")

      # 检查备份目录是否存在
      if not os.path.exists(backup_path) or not os.path.isdir(backup_path):
        error_msg = f"备份目录不存在或不是目录: {backup_path}"
        self.logger.error(error_msg)
        return False, error_msg

      # 如果目标目录已存在，先删除它
      if os.path.exists(restore_to):
        self.logger.info(f"目标目录已存在，正在删除: {restore_to}")
        shutil.rmtree(restore_to)

      # 确保目标目录的父目录存在
      os.makedirs(os.path.dirname(restore_to), exist_ok=True)

      # 复制备份到目标目录
      self.logger.info(f"正在恢复备份: {backup_path} -> {restore_to}")
      shutil.copytree(backup_path, restore_to)

      success_msg = f"恢复成功: {backup_path} -> {restore_to}"
      self.logger.info(success_msg)
      return True, success_msg

    except Exception as e:
      error_msg = f"恢复过程中发生错误: {str(e)}"
      self.logger.error(error_msg, exc_info=True)
      return False, error_msg

  def restore_latest(self) -> Tuple[bool, str]:
    """
    将最新的备份恢复到源目录
    根据备份文件夹的修改时间确定最新的备份，并使用 shutil.copytree 进行恢复

    Returns:
        Tuple[bool, str]: (是否成功, 成功信息或错误信息)
    """
    try:
      # 检查备份目录是否存在
      if not os.path.exists(self.backup_dir):
        error_msg = f"备份目录不存在: {self.backup_dir}"
        self.logger.error(error_msg)
        return False, error_msg

      # 获取最近一次备份文件夹地址
      latest_backup = self.get_latest_timestamped_backup()

      self.logger.info(f"找到最新的备份: {latest_backup}")

      # 如果目标目录已存在，先删除
      if os.path.exists(self.source_dir):
        self.logger.info(f"目标目录已存在，正在删除: {self.source_dir}")
        shutil.rmtree(self.source_dir)

      # 确保目标目录的父目录存在
      os.makedirs(os.path.dirname(os.path.abspath(self.source_dir)), exist_ok=True)

      # 使用 copytree 复制整个目录树
      self.logger.info(f"正在恢复备份: {latest_backup} -> {self.source_dir}")
      shutil.copytree(latest_backup, self.source_dir)

      success_msg = f"恢复成功: {latest_backup} -> {self.source_dir}"
      self.logger.info(success_msg)
      return True, success_msg

    except Exception as e:
      error_msg = f"恢复最新备份时发生错误: {str(e)}"
      self.logger.error(error_msg, exc_info=True)
      return False, error_msg

  def get_latest_timestamped_backup(self) -> Optional[str]:
    """
    查找备份目录中时间戳最新的子文件夹

    子文件夹名称需要以 _YYYYMMDDHHMMSS 格式的时间戳结尾

    Returns:
        Optional[str]: 最新的备份文件夹完整路径，如果没有找到则返回None
    """
    if not os.path.exists(self.backup_dir) or not os.path.isdir(self.backup_dir):
      self.logger.error(f"备份目录不存在或不是目录: {self.backup_dir}")
      return None

    latest_backup = None
    latest_time = None

    for item in os.listdir(self.backup_dir):
      item_path = os.path.join(self.backup_dir, item)
      if not os.path.isdir(item_path):
        continue

      try:
        # 查找最后一个下划线的位置
        last_underscore = item.rfind('_')
        if last_underscore == -1:
          continue

        # 提取时间戳部分（格式：_YYYYMMDDHHMMSS）
        timestamp_str = item[last_underscore + 1:]
        if len(timestamp_str) != 14:  # YYYYMMDDHHMMSS 共14个字符
          continue

        # 解析时间戳
        timestamp = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")

        # 更新最新的备份
        if latest_time is None or timestamp > latest_time:
          latest_time = timestamp
          latest_backup = item_path

      except (ValueError, IndexError) as e:
        self.logger.debug(f"跳过不符合格式的文件夹: {item}, 错误: {str(e)}")
        continue

    if latest_backup:
      self.logger.info(f"找到最新的时间戳备份: {latest_backup} (时间: {latest_time})")
    else:
      self.logger.warning("没有找到符合格式的时间戳备份")

    return latest_backup


# 使用示例
if __name__ == "__main__":
  # 创建备份实例
  backup = SimpleFolderBackup(
    source_dir=r"B:\project\pycharm\mock-api-server\server\data",  # 替换为你要备份的文件夹
    backup_dir=r"B:\project\pycharm\mock-api-server\server\backup"  # 替换为备份存放的目录
  )
