# 消息弹窗暖调统一方案

> 状态：已实施
> 范围：`qt_ui/common_style.py` / `main.py` / `qt_ui/message_box.py`（新增）/ `qt_win/app.py` / `qt_win/output_static_dialog.py` / `qt_ui/server_config_win/module.py` / `qt_ui/download_config_win/module.py` / `qt_ui/list_edit_module/module.py`

## 1. 背景

全项目 `QMessageBox` 静态方法调用 ~15 处（7 文件），渲染为原生 windowsvista 风格，三处"Windows 味"来源：

- **白底原生窗体**：与应用暖调不一致
- **原生标准图标**：蓝 ⓘ / 黄 ⚠ / 红 ✕
- **英文 Yes/No 按钮**：项目未加载 Qt 中文翻译，标准按钮任何系统下均显示英文

调用点分布：`main.py` ×5（already-running/程序异常，全部 `parent=None`）、`app.py` ×4（`show_message_dialog` helper + 两处确认 + 一处 critical）、`output_static_dialog.py` ×4、`qt_ui` 三 module ×5（表单校验/删除确认）。

## 2. 方案：A 打底 + B 做精

### A：`MESSAGE_BOX` QSS 片段（app 级一行覆盖）

- `common_style` 新增 `MESSAGE_BOX` 片段，全部 `QMessageBox` 前缀作用域选择器（不误伤宿主控件）：暖底 `$PANEL_BG`、文字 `$TEXT`、按钮三态同 `button_group` 观感 + `min-width:80px`
- `main.py` 挂接：`app.setStyleSheet(main_win_style.tooltip + MESSAGE_BOX)`——QApplication 级样式表无视父子链，`parent=None` 弹窗亦覆盖，且防御未来漏网点

### B：`qt_ui/message_box.py` helper 统一入口

- `msg_info` / `msg_error` / `msg_question`（返回 `bool`，True=确定）
- 自建 `QMessageBox` + `setIconPixmap`：QPainter 自绘实心圆图标 + 白色字形（info=ACCENT `i`、error=ICON_DANGER `!`、question=ACCENT_DEEP `?`）——静态方法内部建 box 无法替换图标，此为必须走 helper 的原因
- `addButton('确定'/'取消', role)` 中文按钮文本，顺带修复英文 Yes/No；question 默认焦点留"取消"，与原 `default=No` 语义一致
- 返回语义：question 调用点全是 `if reply == QMessageBox.Yes` 同构模式，helper 直接返回 `bool`

### 不做

- 自绘 frameless 圆角弹窗/自定义标题栏：顶层窗透明+圆角在 Windows 有坑（tooltip/QMenu 同类记录），且全体 dialog 原生标题栏保持一致

## 3. 影响面

- 9 文件：common_style/main.py 挂载、helper 新增、7 个调用点文件机械替换
- 行为变化仅限视觉与按钮显示文本（Yes/No→确定/取消），确认语义不变
- excepthook/启动前弹窗：app 级 QSS 在 `QApplication` 创建后即挂，helper 同样可用
- webview 弹窗内 JS `alert/confirm` 不在 Qt QSS 射程，不动
- `QMessageBox` import 从已全量替换的文件移除

## 4. 验收

- `ruff` 归零、pytest 全量过（片段无 `$` 残留由既有用例自动覆盖）
- 真机抽验：退出确认（question）、删除项确认、启动重复运行提示（parent=None 场景）

## 5. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-14 | `MESSAGE_BOX` 片段 + app 级挂接 | common_style 新增片段（`QMessageBox` 前缀作用域：暖底/暖字/按钮三态 + `min-width:80px`）；`main.py` 与 tooltip 合并挂 `QApplication` | QApplication 级无视父子链，`parent=None` 弹窗（启动前检查/excepthook）一并覆盖 |
| 2026-11-14 | `qt_ui/message_box.py` helper | `msg_info`/`msg_error`/`msg_question` 三入口；48px 实心圆图标（info=ACCENT `i` / error=ICON_DANGER `!` / question=ACCENT_DEEP `?`）；`确定`/`取消` 中文按钮修复英文 Yes/No | 图标字形初版用 drawText 字体渲染，改矢量笔画（见方案修正）；question 默认焦点留"取消"与原 `default=No` 对齐 |
| 2026-11-14 | 全量调用点替换 | 7 文件 ~15 处静态调用全换 helper；question 点 `if reply == Yes` → `if msg_question(...)`；`QMessageBox` import 从全替换文件移除 | app.py `show_message_dialog`/output_static 同款 helper 内部分流保留，外层统一走 msg_* |
| 2026-11-14 | 验证 | ruff 归零、pytest 全量过；offscreen 离屏构造验证图标/pixmap/片段渲染；三联图标放大截图目检 | 手码 `QMessageBox` 调用清零（仅 common_style 片段选择器与 helper 内部保留） |

## 6. 方案修正

| 日期 | 原方案 | 实际做法 | 原因 |
|---|---|---|---|
| 2026-11-14 | 图标字形用 `drawText` 字体渲染（QPainter + QFont） | 改矢量笔画绘制（drawArc/drawLine/drawEllipse 组合 `!`/`i`/`?`） | offscreen 验证环境无字体库致字形全 tofu 空框；矢量绘制不依赖字体，任意环境像素级一致，且可离屏目检 |
