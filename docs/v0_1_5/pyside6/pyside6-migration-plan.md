# PySide6 迁移升级方案（PyQt5 → PySide6）

> 状态：已实施（回归验证中）
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
| 2026-10-31 | §4 依赖换绑 | pyproject 改为 `pyside6==6.10.3`，constraints 换 `shiboken6`/`pyside6-essentials`/`pyside6-addons` 三条；`uv sync` 收敛，PyQt5 全部卸载 | — |
| 2026-10-31 | §5 全局替换 + 语义改动 | 17 个手写文件完成：PyQt5→PySide6 import、14 处 Signal、3 处 Slot、8 处 exec_、`triggered[QAction]`→`triggered.connect`、QAction/QShortcut 改道 QtGui、main.py 高 DPI 改专用 API + 补 `AA_ShareOpenGLContexts` | — |
| 2026-10-31 | §6 win_ui.py 重生成 | 7 个目录 pyside6-uic 重生成成功；**main_win 的 .ui 落后于生成物**（不含 MCP 控件），按 §12-修正回滚为旧生成文件 + import 换绑 | 详见 §12 |
| 2026-10-31 | 冒烟验证 | `ruff check` 全绿（新增 `qt_ui/**/win_ui.py` per-file-ignores）；`MainWindow` 等全模块 import 通过；QWebEngineView+QWebChannel 实测 UA=`Chrome/134.0.0.0`；`main.py` 正常启动进入主窗口 | — |
| 2026-10-31 | `win_ui.ui` 修复 + 再生成 | 按 §12-修正2 补齐 .ui（窗口高 370→460、【服务配置】区块整体 +80px、补入 MCP 三控件、移除死控件 cacheCheckBox）后 pyside6-uic 再生成；语义对比验证：控件名集合/geometry/resize 与旧版完全一致，文案/数值属性逐字一致 | `main.py` 复验启动正常 |
| 2026-10-31 | 深色模式样式修复 | `main.py` 增加 `app.setStyle('windowsvista')`：Qt6 默认 windows11 样式跟随系统深色模式返回 dark palette（WindowText=白），与本应用橙色底样式表冲突导致字体发白；windowsvista 固定浅色 palette 且控件绘制与 Qt5 一致（SpinBox 按钮等） | 详见 §12-修正3 |
| 2026-10-31 | 退出卡死修复 ×2 | ① `module/app_server.py` `Process` 加 `daemon=True`：修复非 daemon 子进程残留导致解释器退出时 multiprocessing atexit `join` 无限等待（py-spy 验证杀子进程后主进程立即退出）；② `qt_win/app.py` `_cleanup_in_thread` 加 8s `os._exit` 看门狗 + `_on_cleanup_done` 先销毁存活 WebView 弹窗再 `quit()`：修复开过 WebView 后 `app.exec()` 不退出（原生栈显示事件循环在 MsgWait 空闲等待、quit 未生效） | 详见 §12-修正4/5；复测开关 WebView 后 X 关闭正常 |
| 2026-10-31 | 退出卡死真因定位与根治 | 二分定位（裸 QApplication/单实例/splash/app_server/裸窗口逐级豁免，锁定 MainWindow 显示）+ py-spy `--native` 抓到决定性栈：`quit()` → `processApplicationTermination` → `tryCloseAllWidgetWindows` → `MainWindow::closeEvent` → 二次弹确认框/`event.ignore()` 嵌套事件循环。修复：`closeEvent` 增加 `_exit_finished` 分支——清理完成后接受 Qt 退出路径派发的关闭事件。临时冒烟（模拟确认→蒙层→清理→quit）实测进程自行 `EXIT_CODE=0`、看门狗未触发 | 详见 §12-修正6；修正5 的 WebView 假设被推翻，看门狗/弹窗销毁作为兜底保留 |

## 12. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| 2026-10-31 | 初稿 | — |
| 2026-10-31 | `qt_ui/main_win/win_ui.py` 不由 .ui 重生成，改为还原 HEAD 版本 + 仅换 `from PyQt5` → `from PySide6` import | main_win 的 `win_ui.ui` 落后于已提交生成物（不含 MCP 服务相关的 8 个控件属性：`mcpServerButton`/`mcpServerPortSpinBox`/2 组 layout widget/2 个 label），此前生成物系绕过 .ui 直接修改。重生成会导致 `app.py` 引用缺失（实测 AttributeError 崩溃）。其余 7 目录 .ui 与生成物一致，正常重生成。`.ui` 源文件补全属既有技术债（评审报告已标记生成物入库问题），建议后续用 pyside6-designer 补齐 main_win 的 MCP 控件。 **已被下一条修正取代** |
| 2026-10-31 | 修正2：`win_ui.ui` 直接修复为与运行时 UI 一致，`win_ui.py` 恢复由 .ui 正常生成 | .ui 与生成物失配含两处：① MCP 新增区块（label_mcp / mcp_port 容器 / mcp_btn 容器）从未入 .ui；② 【服务配置】区块整体下移 80px + 窗口加高至 460 未回写 .ui；另发现 .ui 内存在未落地死控件 `cacheCheckBox`/`horizontalLayoutWidget_11`（旧 .py 与代码均无引用），一并以「忠实还原当前运行时 UI」原则移除。修复后控件树与旧 .py 语义级一致，.ui 重新成为可信源文件 |
| 2026-10-31 | 修正3：`main.py` 固定 `windowsvista` 样式 | §9 风险表已预判「windows11 样式差异」，实测比预期严重：深色系统下 windows11 样式返回 dark palette（WindowText=#fff），叠加应用自定义浅色背景样式表导致字体近不可读、SpinBox 呈现代内嵌按钮样式。`setStyle('windowsvista')` 固定浅色 palette 并恢复 Qt5 控件观感 |
| 2026-10-31 | 修正4：`module/app_server.py` 子进程改 daemon | 既有隐患非 Qt6 回归：app_server `Process` 非 daemon 且主进程不留引用，`shutdown_local_server` 按端口 LISTEN 者 terminate——Windows 下 Flask `SO_REUSEADDR` 允许孤儿与新子进程同端口共存，调试期反复强杀遗留孤儿抢占端口匹配，真子进程漏杀 → 解释器退出时 `multiprocessing` atexit 对非 daemon 子进程 `join` 无限等待 → 窗口冻结在退出蒙层。`daemon=True` 后收尾直接 terminate，且杜绝新孤儿 |
| 2026-10-31 | 修正5：`qt_win/app.py` 退出加看门狗 + 先销毁 WebView 弹窗 | 开过 WebView 弹窗后点 X 卡住：py-spy native 栈显示主线程停在 `QCoreApplication::exec → QEventLoop::exec → NtUserMsgWaitForMultipleObjectsEx`，事件循环空闲但 `quit()` 未生效（最小复现未重现，机制未完全定位，疑似 QtWebEngine 消息泵集成影响）。处理：`_on_cleanup_done` 先 `close()+deleteLater()` 两个 WebView 弹窗并 `processEvents` 再 `quit()`；`_cleanup_in_thread` 发出 done 前启动 8s `threading.Timer(os._exit)` 看门狗兜底，触发时写日志。**「机制未定位」部分已被修正6 取代：真因与 WebEngine 无关，看门狗与弹窗预销毁仍作为兜底保留** |
| 2026-10-31 | 修正6：`closeEvent` 增加 `_exit_finished` 放行分支（退出卡死真因根治） | 真因：Qt6 的 `QApplication.quit()` 会走 `processApplicationTermination → tryCloseAllWidgetWindows`，向所有可见顶层窗口派发关闭事件；`MainWindow::closeEvent` 第二次进入时因 `_exit_overlay` 已存在而 `event.ignore()`——窗口拒绝关闭会**取消整个 quit**，事件循环回到空闲等待 → 看门狗兜底才退出（此前「quit 不生效」的表象）。Qt5 的 quit 不派发关闭事件，故旧版无此问题，属 Qt6 行为差异放大的既有代码隐患。修复：`__init__` 增加 `_exit_finished` 标志，`_on_cleanup_done` 置位后 `quit()`；`closeEvent` 首分支检查该标志直接 `event.accept()`。二分期间的全部实验开关（EARLY_QUIT/S1~S3/MID/SKIP_*/PLAIN_SHOW/AUTO_QUIT_MS）与 `@@debug` 日志已清理 |
| 2026-10-31 | 修正7：`QFileDialog` 静态方法 kwargs `directory=` → `dir=`（3 处） | PySide6 将 `getExistingDirectory`/`getOpenFileNames`/`getOpenFileName` 的关键字参数 `directory` 更名为 `dir`（`filter`/`caption` 保留）。PyQt5 写法在 PySide6 下抛 `unsupported keyword` TypeError → 全局异常钩子 → 应用退出，表现为「文件→选择工作目录」闪退。回归期发现，全局扫描共 3 处：`qt_win/app.py`、`qt_win/output_static_dialog.py` ×2 |
| 2026-11-01 | 修正8：`main.py` 补 `QTWEBENGINE_CHROMIUM_FLAGS=--in-process-gpu` | webview 打开状态下画面周期性闪一下：Qt6 WebEngine 在 Windows 上跨进程 GPU 纹理共享存在帧同步缺陷，Qt5 呈现路径不同故旧版无此问题；上游同类 issue（QTBUG-142355 frame jumping / QTBUG-143883，影响至 6.10.1）均未修复，6.8.0 仅修了「添加 view 时整窗闪」（QTBUG-119221/121181）。环境变量二分验证：`--disable-gpu-compositing` 不闪但页面渲染退化变卡（定位 GPU 合成路径）→ `--disable-direct-composition` 仍闪 → `--use-angle=gl` 页面无法渲染 → `--in-process-gpu` 不闪且流畅。落地 `main.py` 顶部（QApplication 创建前），`setdefault` 保留外部显式覆盖能力；后续 Qt 版本修复后可移除 |
