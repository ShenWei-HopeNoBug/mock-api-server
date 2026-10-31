# PySide6 迁移升级方案（PyQt5 → PySide6）

> 状态：待实施
> 范围：`pyproject.toml` / `uv.lock` / `main.py` / `qt_win/*.py` / `qt_ui/*` / `lib/{app_lib,splash,TInteractObject,webview_lib}.py`
> 前端仓库 `mock-api-server-web-v3` 本版零改动（ant-design-vue 维持 3.2.20）

## 1. 背景

当前 PyQtWebEngine 5.15.7 捆绑的 Qt 二进制为 5.15.2，内嵌内核 **Chromium 83.0.4103.122**（2020 年）：

- ant-design-vue 4.x 改用 cssinjs 运行时注入样式，生成选择器依赖 `:where()`（需 Chrome 88+）等现代 CSS 特性，在 Chromium 83 上样式大面积异常，内嵌 web 被迫停留在 antdv 3.2.20；
- CSS 选择器兼容性无法靠 `@vitejs/plugin-legacy` / polyfill 降级，前端侧无解，只能升级内核；
- PyQt5 线内核已冻结：`pyqtwebengine-qt5` 无 win_amd64 新 wheel（`pyproject.toml` constraint 注释有记录），Qt5 内不存在升级路径。

## 2. 目标与拆分

- **本方案范围**：客户端 Qt 绑定整体迁移 PyQt5 → PySide6 **6.10.3**（Qt 6.10，QtWebEngine 内核 Chromium 134，支持 Python 3.13）；
- **非目标**：前端 antdv 4.x 升级（内核稳定后独立迭代）；`qt_ui/*/win_ui.py` 生成物入库治理（评审报告已标记，本版维持入库现状仅更换生成器）；PyInstaller 打包流程不变。

## 3. 选型结论

| 对比项 | PySide6（选定） | PyQt6 |
|---|---|---|
| 许可证 | LGPL v3，闭源分发友好 | GPL v3 / 商业许可 |
| 维护方 | Qt 公司官方 | Riverbank |
| 枚举写法 | `Qt.AlignCenter` 短写法与全限定写法均兼容 | 必须全限定 `Qt.AlignmentFlag.AlignCenter` |
| 信号/槽 | `Signal` / `Slot` | `pyqtSignal` / `pyqtSlot`（与现状同名） |
| 信号重载下标 | 不支持 | 支持（`triggered[QAction]`） |

选定 PySide6 的核心收益：**约 51 处 `Qt.*` 枚举与 `QMessageBox.Yes/No` 等用法零改动**，迁移面收敛为 import 更名 + 信号声明更名；另解决 GPL 分发灰色地带。代价仅 `Signal`/`Slot` 更名与 1 处 `triggered[QAction]` 改写。

## 4. 依赖改动

`pyproject.toml`：

```toml
# dependencies 移除：
#   "pyqt5==5.15.11",
#   "pyqtwebengine==5.15.7",
# dependencies 新增：
  "pyside6==6.10.3",

# constraint-dependencies 移除：
#   "pyqt5-qt5==5.15.2", "pyqt5-sip==12.17.0", "pyqtwebengine-qt5==5.15.2",
# constraint-dependencies 新增（钉死二进制/绑定生成器传递依赖，沿用现有约束模式）：
  "shiboken6==6.10.3",
  "pyside6-essentials==6.10.3",
  "pyside6-addons==6.10.3",
```

说明：

- `pyside6` 为 meta 包 = `pyside6-essentials` + `pyside6-addons`；QtWebEngineWidgets / QtWebEngineCore / QtWebChannel 均位于 Addons（6.10 线尚未拆分独立 wheel，**6.12 起 WebEngine 拆分为 `PySide6_WebEngine` 独立包**，本版不涉及）；
- `shiboken6` 替代 `pyqt5-sip` 作为绑定层，需纳入约束；
- 无 `import sip` 直接用法，绑定层替换对代码透明。

## 5. 代码改动清单

全仓 `from PyQt5` 共 25 个文件：17 个手改 + 8 个 `qt_ui/*/win_ui.py` 由 `pyside6-uic` 重新生成（§6）。

### 5.1 全局机械替换

| 改动 | 位置 | 说明 |
|---|---|---|
| `from PyQt5.X` → `from PySide6.X` | 17 个手写文件 | 模块名一一对应：`QtCore`/`QtGui`/`QtWidgets`/`QtWebChannel`/`QtWebEngineWidgets` |
| `pyqtSignal` → `Signal` | `lib/TInteractObject.py` ×2、`qt_win/app.py` ×7、`lib/splash.py` ×1、`qt_win/text_input_dialog.py` ×1、`qt_win/output_static_dialog.py` ×2、`qt_win/download_proxy_config_dialog.py` ×1（共 14 处） | `x: pyqtSignal = pyqtSignal(str)` → `x: Signal = Signal(str)` |
| `@pyqtSlot` → `@Slot` | `lib/TInteractObject.py` ×3 | 用法一致 |
| `exec_()` → `exec()` | `qt_win/app.py` ×5（L205/209/213/248/553）、`qt_ui/list_edit_module/module.py` ×2（L122/157）、`main.py` ×1（L98） | Qt6 官方写法 |

### 5.2 语义级改动

| 文件 | 现状 | 改为 | 原因 |
|---|---|---|---|
| `lib/app_lib.py:14` | `from PyQt5.QtWidgets import QAction, ...` | `from PySide6.QtGui import QAction` | Qt6 将 QAction 移至 QtGui |
| `lib/app_lib.py:264` | `menu.triggered[QAction].connect(cb)` | `menu.triggered.connect(cb)` | PySide6 无信号下标语法；Qt6 `triggered` 仅 `QAction*` 一个签名 |
| `lib/webview_lib.py:8` | `from PyQt5.QtWidgets import ..., QShortcut, ...` | `from PySide6.QtGui import QKeySequence, QShortcut`（QKeySequence 原本在 QtGui，拆分两行） | Qt6 将 QShortcut 移至 QtGui |
| `main.py:48` | `QGuiApplication.setAttribute(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)` | 删除 | Qt6 默认即 PassThrough 且高 DPI 恒开启 |
| `main.py` | 无 | `QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)`（`QApplication(sys.argv)` 之前） | Qt6 WebEngine Widgets 官方要求 |

### 5.3 PySide6 兼容、零改动清单

- 全部 `Qt.*` 枚举短写法（~51 处）：`AlignCenter` / `WindowModal` / `CustomContextMenu` / `WindowContextHelpButtonHint` / `WindowMinMaxButtonsHint` / `FramelessWindowHint` / `WindowStaysOnTopHint` / `Window` / `WA_TranslucentBackground` / `SolidLine` / `RoundCap` / `PointingHandCursor` / `LeftButton` / `TextBrowserInteraction` / `HighDpiScaleFactorRoundingPolicy`（枚举本身仍在，仅调用方式变化）；
- `QPainter.Antialiasing`、`QMessageBox.Yes/No`、`QMessageBox.question(...)`；
- `QSharedMemory` 单实例检测、`win32gui`/`win32con` 置顶、`multiprocessing` 子进程体系；
- `QWebEngineView` 全部 API：`page()` / `setZoomFactor` / `setDevToolsPage` / `loadFinished` / `customContextMenuRequested` / `load(QUrl)`；
- `QWebChannel` + `TInteractObj` 桥接协议；前端 `qrc:/qtwebchannel/qwebchannel.js` 资源路径 Qt6 不变。

### 5.4 改动文件总表（17 个手写文件）

`main.py`、`qt_win/{app,about_dialog,download_config_dialog,download_proxy_config_dialog,mitmproxy_config_dialog,mitmproxy_data_edit_dialog,output_static_dialog,server_config_dialog,text_input_dialog}.py`、`lib/{app_lib,splash,TInteractObject,webview_lib}.py`、`qt_ui/{list_edit_module,server_config_win,download_config_win}/module.py`

## 6. win_ui.py 重新生成

`.ui` 源文件不动，逐目录执行：

```bash
uv run pyside6-uic qt_ui/main_win/win_ui.ui -o qt_ui/main_win/win_ui.py
# 同法处理：about_win / download_config_win / list_edit_module /
# mitmproxy_config_win / output_static_win / server_config_win / text_input_win
```

diff 校验点：生成物 import 变为 `from PySide6 import QtCore, QtGui, QtWidgets`，控件树/属性与旧版一致。

## 7. 实施顺序

```
pyproject.toml 改依赖 → uv sync → pyside6-uic --version 验证工具链
  → 全局替换（PyQt5→PySide6 / pyqtSignal→Signal / pyqtSlot→Slot / exec_→exec）
  → §5.2 语义改动（app_lib / webview_lib / main.py）
  → §6 重生成 8 个 win_ui.py
  → uv run python main.py 开发模式跑通（剩余问题以 ImportError/AttributeError 逐个暴露收敛）
  → §8 回归矩阵人工验收
  → uv run python build.py 打包 + 双 exe 冒烟
  → 文档对齐（README、CHANGELOG、版本号）
```

## 8. 回归验证矩阵

| 项 | 验证点 |
|---|---|
| 主窗口 | 显示/菜单栏/退出确认/退出蒙层动画/resizeEvent 蒙层跟随 |
| 原生弹窗 | about / download_config / mitmproxy_config / output_static / server_config（含 list_edit、text_input 联动） |
| webview 弹窗 | 抓包数据管理、下载代理配置：页面渲染、loading 占位切换、F12 DevTools、UA 确认 `Chrome/134` |
| 桥接 | 数据列表拉取、增删改查、`download_proxy.close_requested` 单向事件关窗 |
| 单实例 | 二次启动检测 + 已有窗口置顶（`QSharedMemory` + `win32gui`） |
| 高 DPI | 100%/125%/150% 缩放下窗口尺寸与 webview `setZoomFactor`（Qt6 高 DPI 策略差异重点验证） |
| 服务联动 | mock / mitmproxy / MCP 三子进程启停 + 退出清理 |
| 打包 | 双 exe（有/无黑窗）均可启动；webview 正常渲染（`QtWebEngineProcess.exe` 被 hooks 收集）；包体增量确认 |

## 9. 影响面与风险

| 项 | 说明 |
|---|---|
| 代码改动量 | 17 文件 ~30 处编辑点 + 8 个重生成文件 + pyproject；全部为 fail-fast 型改动（import/枚举错误启动即暴露） |
| 包体 | Qt6 全家桶较 Qt5 增大约 +50~100MB（site-packages 目录） |
| 系统要求 | Qt6 最低 Windows 10，若有 Win7/8.1 存量用户需公告 |
| UI 观感 | Qt6.7+ Windows 默认启用 windows11 样式，原生控件外观可能微调；webview 内 antdv 页面不受影响 |
| 高 DPI | Qt6 高 DPI 恒开 + PassThrough 默认，与 Qt5 行为可能产生像素级尺寸差异，按矩阵验证 |
| 打包 | pyinstaller-hooks-contrib 对 PySide6 + WebEngine 支持成熟；`build.py` 的 spec 改写复用套路与绑定层无关，预期无需改动，实测确认 |
| 许可证 | GPL → LGPL，分发约束放宽，属正向变化 |

## 10. 回滚

依赖全量走 `uv.lock` 快照，代码改动集中于 import/信号声明层，无数据迁移、无协议变更、前端零依赖。**回滚 = 还原工作区 + `uv sync`**，零成本。

## 11. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-10-31 | 方案定稿 | 选型 PySide6 6.10.3；影响面全量扫描完成（25 个 PyQt5 import 文件、14 处 Signal、3 处 Slot、8 处 exec_、1 处 triggered 下标、2 处 import 改道） | 待实施 |

## 12. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| 2026-10-31 | 初稿 | — |
