---
trigger: manual
---

# 项目技术栈

- python 3.13 + PySide6 6.10（Qt6，内嵌 WebEngine 内核 Chromium 134）+ sqlite3
- 桌面端结构：`qt_win/` 为窗口逻辑层，`qt_ui/` 为界面层（`.ui` 源文件 + `pyside6-uic` 生成物 + 样式文件）

# 代码规范

## 注释规则

- 函数：函数上方用 `#` 单行注释简述功能（如 `# 启动mock服务`），不用太长；仅复杂逻辑用 docstring
- 变量：含义无法从命名看出的重要变量注释用途/取值（如状态机枚举值）
- 代码块分组可用 `'''...'''` 单行块注释（如 `'''按钮事件绑定'''`）
- 注释说明「是什么/为什么」，不复述代码本身；统一用中文

## 类型定义规则

- 当前项目 python 3.13，`int | float`、`list[str]` 等新语法可用；写法风格跟随所在文件现状（存量代码多用 `Optional`/`List`）
- 变量、参数、返回值的类型定义尽量准确；复杂 dict 统一抽象成 `TypedDict` 放进 `app_types/` 按业务域分文件（如 `mcp_server_types.py`），可选字段用 `total=False`，字段含义不直观时加行内注释
- 已有符合语义的类型定义优先复用；没有明确要求不要改动已有类型定义

## Qt / PySide6 使用约定

- 信号/槽用 `Signal` / `Slot`（不是 `pyqtSignal` / `pyqtSlot`）；进入事件循环用 `exec()`（不是 `exec_()`）
- `QAction`、`QShortcut`、`QKeySequence` 从 `PySide6.QtGui` 导入；菜单 `triggered` 信号直接 `.connect(callback)`，不支持 `triggered[QAction]` 下标语法
- `QFileDialog` 静态方法（`getExistingDirectory` / `getOpenFileName` / `getOpenFileNames`）的目录参数名是 `dir`，不是 `directory`
- `qt_ui/*/win_ui.py` 是 `pyside6-uic` 由 `.ui` 生成的文件，不要手改；改界面先改 `.ui` 再重新生成：`uv run pyside6-uic qt_ui/<目录>/win_ui.ui -o qt_ui/<目录>/win_ui.py`
- 应用在 `main.py` 固定 `windowsvista` 样式：Qt6 默认 windows11 样式会跟随系统深色模式返回深色 palette，与自定义浅色样式表冲突导致白字/控件观感异常，改动前先确认意图
- `multiprocessing.Process` 必须 `daemon=True`，否则退出阶段 multiprocessing atexit 会对存活子进程无限 join 导致窗口卡死；注意 daemon 进程禁止再创建孙进程（`AssertionError: daemonic processes are not allowed to have children`），若未来启用 Flask/uvicorn reloader、多 worker 或 mitmproxy wireguard 等会 spawn 子进程的模式，须先评估改回非 daemon 的退出挂死风险
- `QApplication.quit()` 会向所有顶层窗口派发关闭事件；`closeEvent` 中 `event.ignore()` 会取消整个退出流程，确认退出后放行需 `event.accept()`
- 日志架构：文件/控制台 handler 仅 GUI 主进程持有（`configure_logging('parent')`），子进程只把 LogRecord 经 `mp.Queue` 交父进程统一落盘——多进程共写 `app.log` 会在轮转 rename 时 PermissionError 且静默丢日志。新增 `Process` 必须 args 传 `get_log_queue()`，入口函数首行 `configure_logging('child', log_queue)`（包 try/except，失败不拖死服务）；`logger_lib` 模块级禁止建文件 handler

## 新生成的代码

- 没有特别要求时：函数/变量的注释遵循「注释规则」，类型标注遵循「类型定义规则」，Qt 写法遵循「Qt / PySide6 使用约定」
- 缩进统一 2 空格，新文件带 `# -*- coding: utf-8 -*-` 头；命名与其余风格跟随所在文件既有写法
