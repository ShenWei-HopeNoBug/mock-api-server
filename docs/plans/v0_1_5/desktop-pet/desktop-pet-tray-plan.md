# 桌宠模式系统托盘接入方案

> 状态：待实施
> 关联：[desktop-pet-service-menu-plan](desktop-pet-service-menu-plan.md)

## 1. 背景与目标

桌宠窗口是 `Qt.Tool`（无任务栏入口），主面板隐藏后用户对进程完全失控——桌宠异常时只能任务管理器强杀。本方案在桌宠模式下挂系统托盘图标，提供恢复主面板与退出（含强制退出）入口。

## 2. 范围

- **仅桌宠模式显示托盘**：`enter_pet_mode` 时 `tray.show()`，`exit_pet_mode` 时 `tray.hide()`；主面板模式不常驻（常驻=删一行 hide，暂不做）
- 托盘菜单：服务快捷项（复用 `_build_pet_service_menu`）+ 打开主面板 + 正常退出 + 强制退出

## 3. 结构

```python
self._tray: Optional[QSystemTrayIcon] = None

def _ensure_tray(self):
    if self._tray is None and QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(QIcon(app_env.APP_ICON), self)
        tray.setToolTip('mock-api-server')
        menu = QMenu(); apply_pet_menu_style(menu)      # 持久菜单
        menu.aboutToShow.connect(self._rebuild_tray_menu)  # 每次弹出前重建，防快照过期
        tray.setContextMenu(menu)
        tray.activated.connect(...)                     # 左键 → exit_pet_mode
        self._tray = tray
```

生命周期：`_ensure_tray()` 懒建 + `isSystemTrayAvailable()` 兜底降级；`aboutToQuit` 与 `_on_cleanup_done` 各 `hide()` 一次——**进程退出前必须隐藏托盘图标，否则 Windows 留幽灵图标**。

## 4. 菜单复用与改造

- `pet_shell.py` 抽 `apply_pet_menu_style(menu)`（无边框/透明/QSS 三行），`contextMenuEvent` 与托盘菜单共用；
- 托盘菜单每次 `aboutToShow`：`clear()` → `_build_pet_service_menu` → 分隔线 → 打开主面板/退出/强制退出；
- `_build_pet_service_menu` 内 `QTimer` 增加 `menu.aboutToHide` → `stop() + deleteLater()`：托盘菜单持久复用，不自清会累积死 timer。

## 5. 菜单项

| 项 | 行为 |
|---|---|
| 三服务项 | 原样复用（标签/图标/禁用矩阵一致） |
| 打开主面板 | `exit_pet_mode` |
| 退出 | `quit_from_pet`（正常确认 + 清理流水线） |
| 强制退出 | `os._exit(0)`：跳过一切清理，正常流程失效时的最后手段 |

左键单击托盘图标 → `exit_pet_mode`（快于右键开菜单）。

**强杀的诚实代价**：`os._exit` 跳过清理，SQLite 写入中途被杀理论上有极小损坏概率（事务保护下很低但非零）——定位"最后手段"，文案标清楚。

## 6. 改动清单

| 文件 | 改动 |
|---|---|
| `qt_win/pet_shell.py` | 抽 `apply_pet_menu_style` + contextMenuEvent 换用（~10 行） |
| `qt_win/app.py` | `_ensure_tray`/`_rebuild_tray_menu` + enter/exit/quit 三处接线 + 服务项 timer 自清（~65 行） |

## 7. 验收

- 点 X 进桌宠 → 托盘出现应用图标 + tooltip
- 左键托盘 → 回主面板，托盘消失
- 托盘菜单样式/服务项/禁用矩阵与桌宠菜单一致
- 「退出」正常确认流程；「强制退出」立即杀死进程（含子进程）
- 退出后无幽灵图标残留
- 无托盘环境降级无报错

## 8. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|

## 9. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
