# 桌宠模式最小闭环方案

> 关联文档：[GUI_STACK_DESKTOP_PET_DISCUSSION.md](../../../discussions/GUI_STACK_DESKTOP_PET_DISCUSSION.md)（选型与可行性背景，含 Live2D 路线评估）
> 状态：待实施
> 范围：`main.py`、`qt_win/app.py`、新增 `qt_win/desktop_pet.py`

## 1. 背景

拟增加桌宠模式：主面板点 X 切换为桌面悬浮小球，双击小球恢复主面板；退出入口移入小球右键菜单。V1 只做最小闭环，顺带借占位圆球验证 Windows 透明区逐像素点击穿透（Live2D 时代的关键技术疑点，见关联讨论 §3.3）。

## 2. 决策

| 项 | 决定 |
|---|---|
| X 行为 | 直接切桌宠，不再弹「确定要退出吗」；退出入口只在桌宠右键菜单 |
| 退出路径 | 桌宠菜单「退出」→ 恢复主面板 → `_force_quit` 标志走现有退出流程（确认框 + 蒙层 + 清理流水线原样复用） |
| 桌宠素材 | QPainter 纯代码绘制占位圆球，不依赖外部素材文件 |
| 右键菜单 | V1 仅「打开主面板」「退出」两项；服务快捷操作后续迭代 |
| 实例管理 | `MainWindow` 懒创建一次，hide/show 复用，不重建 |
| 耦合方式 | 桌宠构造传入 `on_restore`/`on_quit` 回调，不 import `app.py` |

## 3. 改动清单

### 3.1 `main.py`

```python
app.setQuitOnLastWindowClosed(False)
```

防主面板 hide + 顶层弹窗关闭的瞬间 Qt 误判「最后窗口已关」自动 quit，甩出孤儿子进程。

### 3.2 `qt_win/desktop_pet.py`（新增，~120 行）

```python
class DesktopPetWindow(QWidget):
    flags: FramelessWindowHint | WindowStaysOnTopHint | Tool   # Tool 不进任务栏/Alt+Tab
    attr:  WA_TranslucentBackground
    size:  固定 100×100
    构造:  DesktopPetWindow(on_restore: Callable, on_quit: Callable)
```

- **绘制**：`paintEvent` 抗锯齿 + 径向渐变圆（直径 ~80 居中 + 眼睛点缀），四角透明区不绘制任何像素；
- **拖拽**：`mousePressEvent`/`mouseMoveEvent` 记偏移 `move()`；
- **双击**：`mouseDoubleClickEvent` → `on_restore()`；
- **右键**：`contextMenuEvent` → `QMenu[打开主面板, 退出]` → `on_restore()`/`on_quit()`；
- **出生位置**：`move_to_corner()` 按 `screen()->availableGeometry()` 右下角减边距。

### 3.3 `qt_win/app.py`

`__init__` 新增字段：

```python
self._force_quit: bool = False                   # 区分「点X切桌宠」与「桌宠菜单退出」
self._pet: Optional[DesktopPetWindow] = None     # 懒创建复用
```

`closeEvent` 在现有两个前置分支后插入分支（现有确认框→蒙层→清理代码不动）：

```python
if not self._force_quit:           # 普通点 X = 切桌宠
    event.ignore()
    self.enter_pet_mode()
    return
# _force_quit=True：原样走老流程（确认框 → 蒙层 → cleanup → quit）
```

新增三个方法：

```python
def enter_pet_mode(self):     # 点X：藏主面板出桌宠
def exit_pet_mode(self):      # 双击/菜单：pet.hide() + show/raise_/activateWindow 还原
def quit_from_pet(self):      # 菜单退出：_force_quit=True → hide 桌宠 → show 主面板 → close()
```

`close()` 的多义性（X=切桌宠 / 菜单=退出）由 `_force_quit` 标志区分。

## 4. 点穿验证（两阶段）

**阶段一（无 mask 测原生行为）**：四角透明区不绘制像素，实测点透明区鼠标事件是否穿透到下层窗口（桌宠盖桌面图标/浏览器验证）。依据：Windows `WA_TranslucentBackground` 顶层窗走 `UpdateLayeredWindow`，理论未绘制像素天然不命中，Qt6 + 本 flags 组合需实测。

**阶段二（兜底保证可用）**：阶段一不生效则加一行 `self.setMask(QRegion(ball_rect, QRegion.Ellipse))`——Windows 下 setMask 同时裁剪绘制与输入命中区域，圆形必穿透；代价是边缘无抗锯齿羽化，占位球可接受。

**结果回填**：验证结论记入关联讨论文档 §6 待验证清单——穿透生效则 Live2D 不规则形状零成本逐像素命中，不生效则 Live2D 须走 `setMask` 路线。

## 5. 影响面与边界

| 项 | 说明 |
|---|---|
| 服务层 | 零改动：三服务为独立 daemon 子进程，主面板隐藏期间照跑；状态 Signal 与可见性解耦，恢复后按钮态自然正确 |
| 退出清理 | 复用现有 `_cleanup_in_thread`/`_exit_overlay`/`_exit_finished` 流水线，零新增退出路径 |
| 二次启动（单实例） | `bring_to_front` 只枚举可见窗口 → 置顶桌宠唤不出主面板，V1 接受（双击恢复）；后续可 QLocalSocket 发「恢复」指令 |
| 切桌宠时开着 WebView 弹窗 | WindowModal 弹窗可能残留可见，V1 不管（仍可用）；后续 `enter_pet_mode` 可统一 close 顶层 dialog |
| 清理中点 X / 清理期双击桌宠 | 现有 `_exit_overlay` 分支已挡；`quit_from_pet` 先 hide 桌宠，竞态窗口极小不管 |
| 高 DPI/多屏 | `PassThrough` 策略已生效；出生位置按 `availableGeometry` 算天然跟随主屏 |

## 6. 验收

| 场景 | 预期 |
|---|---|
| 点 X | 主面板消失，右下角出圆球，任务栏无新增图标，服务状态不掉 |
| 拖/双击球 | 可拖动；双击回主面板且几何位置不变 |
| 右键球 | 菜单弹出；「打开主面板」同双击效果 |
| 菜单「退出」 | 主面板弹出 → 确认框 → 蒙层清理 → 正常退出无孤儿子进程 |
| 点穿测试 | 球盖桌面图标点四角透明区，记录穿透结果及是否启用 setMask 兜底 |
| 服务 RUNNING 切桌宠再切回 | 按钮状态正确 |

```bash
uv run ruff check .   # 保持归零
```

## 7. 明确不做

- 服务快捷操作菜单项（「启动服务」等）、状态联动表情——下一轮迭代；
- Live2D / 帧动画渲染（占位球先验证交互与点穿）；
- 位置记忆、边缘吸附、开机自启、系统托盘；
- 二次启动「恢复主面板」IPC（QLocalSocket）；
- 关闭时统一清理顶层 WebView 弹窗。

## 8. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| - | - | - | - |

## 9. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| - | - | - |
