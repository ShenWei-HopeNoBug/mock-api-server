# 子任务 08 — app.py 改造

## 目标

移除 `qt_win/app.py` 中的缓存模式 UI 逻辑，新增 `close_all_mock_db` 调用以在应用退出时触发最终 checkpoint。

## 涉及文件

- `qt_win/app.py`

## 移除缓存模式 UI 逻辑

- 移除 `self.cache: bool = False` 属性及注释
- 移除 `cache_checkbox_click` 回调函数
- 移除 `self.cacheCheckBox.setChecked(self.cache)` 和 `self.cacheCheckBox.clicked.connect(cache_checkbox_click)` 信号绑定
- 移除两处 `self.cacheCheckBox.setDisabled(disabled)` 调用
- `server_config` 字典中移除 `"read_cache": self.cache` 字段
- `server_process_start` 函数中移除 `read_cache = server_config.get('read_cache', False)`，`server.start_server()` 调用去掉 `read_cache` 参数

## 新增 `close_all_mock_db` 导入与调用

在 `closeEvent` 中用户确认退出后、设置 `client_exit` 全局变量前，调用 `close_all_mock_db()` 关闭主进程所有 `MockDB` 连接，触发最终 checkpoint 将 `-wal` 合并回主库：

```python
from lib.app_lib import close_all_mock_db

def closeEvent(self, event: QCloseEvent):
  reply = QMessageBox.question(...)
  if reply == QMessageBox.Yes:
    self.stop_catch_server()
    self.stop_server()
    self.stop_app_server()
    # 关闭主进程所有 DB 连接，触发最终 checkpoint
    close_all_mock_db()
    GLOBALS_CONFIG_MANAGER.set(key='client_exit', value=True)
    time.sleep(0.5)
    event.accept()
  else:
    event.ignore()
```

### `close_all_mock_db` 的调用位置

放在 `stop_catch_server()` / `stop_server()` / `stop_app_server()` 之后，确保子进程已停止、不再有并发 DB 写入；放在 `GLOBALS_CONFIG_MANAGER.set(key='client_exit', value=True)` 之前，确保 checkpoint 在进程退出前完成。
