# 子任务 09 — mitmproxy_data_edit_dialog 改造

## 目标

移除 `qt_win/mitmproxy_data_edit_dialog.py` 中的 `SimpleFolderBackup` 相关代码。

## 涉及文件

- `qt_win/mitmproxy_data_edit_dialog.py`

## 改动内容

- 移除 `from lib.backup_lib import SimpleFolderBackup` 导入
- 移除 `from config.work_file import (DATA_DIR, BACKUP_DIR, USER_API_FILE_NAME)` 中仅用于备份的 `DATA_DIR` / `BACKUP_DIR` / `USER_API_FILE_NAME` 导入（这三个常量仅用于 `SimpleFolderBackup` 的 `source_dir` / `backup_dir` / `watch_backup_files`，移除备份后无其他引用）
- 移除 `__init__` 中 `source_dir` / `backup_dir` 变量及 `self.simple_folder_backup` 实例创建
- 移除 `init()` 后的 `self.simple_folder_backup.watch_diff_backup()` 调用
- 移除 `closeEvent` 中 `self.simple_folder_backup.watch_diff_backup()` 调用，仅保留 `event.accept()`

## 原因

与 `request_catch.py` 同理，WAL 模式下 `copytree` 无法保证 SQLite 一致性，备份功能后续用 SQLite 原生 API 重新实现。
