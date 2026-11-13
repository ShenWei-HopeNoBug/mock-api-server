# GUI 技术选型与桌宠模式可行性讨论报告

> 讨论日期：2026-11-14
> 参与者：项目作者 × Devin
> 性质：思维碰撞记录，非实施承诺；后续结论若立项实施，以 `plans/` 正式方案为准

## 1. 背景与议题

项目立项时因核心抓包库（mitmproxy）为 Python 技术栈选定 PyQt5，后升级 PySide6。现拟增加**桌宠模式**：主面板可切换为 Live2D 驱动的桌面小人，右键唤出菜单快捷启停服务，双击打开主面板（形态参考百度网盘/迅雷/搜狗输入法悬浮工具）。

两个议题：

- **议题一**：桌宠模式在当前 PySide6 栈下的可行性与难点分布；
- **议题二**：主流桌面 GUI 栈横评，校验本项目选型是否最优，并为后续新项目立项留参考。

## 2. 现状架构对桌宠的适配评估

| 层面 | 现状 | 对桌宠的影响 |
|---|---|---|
| 服务控制 | mock / mitmproxy / MCP 三服务均为 `MainWindow` 方法 + `READY/START_WAIT/RUNNING/STOP_WAIT` 状态机 + Signal 驱动 UI（`qt_win/app.py`） | 桌宠与主窗口同进程，右键菜单可直接调 `server_button_click()` 等，子进程管理、端口检查、中间态零成本复用；订阅状态 Signal 即可驱动小人表情/动作切换 |
| UI 层 | `pyside6-uic` Widgets 主面板 + 部分 `QWebEngineView` 弹窗（数据管理台） | WebEngine 已随包分发，但桌宠渲染不建议走 webview（见 §3.2） |
| 内部 API | `module/app_server` Flask 服务支撑 web 弹窗 | 说明 UI/核心已部分解耦，理论上换 GUI 栈有对接路径，但不构成换栈理由 |
| 生命周期 | 无系统托盘；`closeEvent` 走完整清理退出 | 需新增 QSystemTrayIcon + 「关闭主面板→隐藏到桌宠」模式分支，属小改造 |

**结论**：现有架构是利好而非障碍——服务控制层信号-槽解耦充分，桌宠本质是把主面板按钮挪进悬浮窗菜单，核心逻辑零 IPC 成本复用。

## 3. 桌宠功能分层难度评估

### 3.1 交互壳：全部低风险

| 需求 | 实现 | 难度 |
|---|---|---|
| 无边框透明悬浮窗 | `FramelessWindowHint + WindowStaysOnTopHint + Tool + WA_TranslucentBackground` | ★ |
| 拖拽移动 | `mousePressEvent`/`mouseMoveEvent` 记偏移 | ★ |
| 右键快捷菜单 | `contextMenuEvent` 弹 `QMenu`，复用服务控制方法 | ★ |
| 双击唤主面板 | `mouseDoubleClickEvent` → `show()` | ★ |
| 边缘吸附/位置记忆 | 几何计算 + `HISTORY_CONFIG_MANAGER` 持久化 | ★★ |
| 开机自启 | 注册表 Run 键 | ★ |

### 3.2 核心难点一：Live2D 渲染路线

Live2D Cubism SDK 官方仅 C++/Native/Web 版，**Python 无官方绑定**，三条路线：

**路线 A：`live2d-py` + `QOpenGLWidget`（推荐优先验证）**

- 社区 C 扩展封装 Cubism Native SDK，官方示例即 PySide6 + `QOpenGLWidget`；支持视线跟踪、部件级点击检测、动作/表情/物理/口型，Cubism 3.0+ 模型兼容；轻量、无新进程
- 风险：① 社区项目，维护性与 Cubism 5 新模型兼容性存疑；② 已知坑——v3 透明背景需 `setAutoFillBackground(False)` + 特定 `QSurfaceFormat` 配置，高 DPI 下命中坐标需乘缩放因子；③ PyInstaller 需打入 Cubism Core DLL

**路线 B：`QWebEngineView` + pixi-live2d-display（不推荐）**

Qt6/Windows 下 `page()->setBackgroundColor(transparent)` 透明 webview 至今仍不稳定（约 50% 概率渲染异常的社区报告），且项目已因 QTBUG-142355 类 GPU 闪帧问题打过 `--in-process-gpu` 补丁——透明悬浮窗此类非常规用法踩 GPU 合成 bug 概率高，还多养一个渲染进程。

**路线 C：帧动画兜底（务实 Plan B）**

百度网盘/迅雷悬浮球、开源桌宠 VPet 实为序列帧而非 Live2D。`QMovie`（APNG/WebP/GIF）或自绘 sprite 即可支撑「待机/运行中/拖动」状态切换，零依赖零风险。若 Live2D 的视线跟随/可交互非硬需求，性价比最高。

### 3.3 核心难点二：逐像素点击穿透

- 利好：Windows 下 `WA_TranslucentBackground` 顶层窗口走 `UpdateLayeredWindow`，未绘制像素天然不参与命中——此点 Qt 优于 Electron（后者需 `setIgnoreMouseEvents` + hover 轮询 hack）
- 不确定点：叠 `QOpenGLWidget` 后合成路径是否保留逐像素命中，须 spike 验证；失效兜底为按渲染帧 alpha 算 `setMask(QRegion)`（Live2D 轮廓变化缓，低频更新可接受）
- 务实视角：紧凑造型（悬浮球/小体积小人）下矩形命中区域本就可用，此坑可能无需填

### 3.4 其他风险项

| 项 | 说明 |
|---|---|
| Live2D 授权 | Cubism SDK 发行许可（个人/小规模免费，商用须签协议）；模型本体用官方示例模型或定制，注意授权条款 |
| PyInstaller | live2d-py native DLL + 模型资源（.model3.json/贴图/motion3.json）进 datas |
| GPU 共存 | 现有 `--in-process-gpu` workaround 与 `QOpenGLWidget`（已开 `AA_ShareOpenGLContexts`）共存性须打包实测 |
| 多屏/DPI | 已设 `PassThrough` 策略；跨屏拖拽、`devicePixelRatio` 下 GL viewport/命中坐标须手动处理 |

## 4. 主流桌面 GUI 技术栈横评

### 4.1 四类路线全景

| 类别 | 代表 | 优势 | 短板 |
|---|---|---|---|
| Qt 系 | PySide6/PyQt6/C++ Qt | 跨平台最成熟、控件最全、自带 WebEngine、PySide6 LGPL 商用友好 | Widgets 默认观感老旧，精美 UI 靠 QSS/自绘/三方库抬；QML 是另一套技能 |
| Web 混合 | Electron / Tauri / pywebview | UI 表现力天花板，Live2D 等 Web 生态最成熟，悬浮类花活最顺手 | Python 核心永远是外挂 sidecar + IPC；Electron 重、Tauri 要 Rust |
| 自绘引擎 | Flutter Desktop / DearPyGui | Flutter 自绘一致性最好；DearPyGui 纯 Python 做工具快 | 桌面窗口魔法（透明/置顶/穿透）靠社区补丁；DearPyGui 审美偏编辑器面板 |
| C# Windows 系 | WPF / WinUI3 / Avalonia | Windows 原生 Fluent 颜值第一梯队；开源桌宠 VPet 即 WPF | mitmproxy 锁死 Python，换 C# 只是 GUI 换皮，核心仍 sidecar，变双语言项目 |

> 参考事实：百度网盘/迅雷/搜狗悬浮窗历史为 C++ DirectUI；QQ NT 迁往 Electron；微信 Windows 4.0 迁至 Qt C++——悬浮形态与具体栈无关，本质是「无边框透明置顶窗 + 自绘」。

### 4.2 PySide6 的 UI 上限问题

**能精美，但要自己抬。** 微信 4.0、Telegram、OBS、DaVinci Resolve、Maya 均为 Qt。抬上限三档：

1. **QSS**（CSS 子集）：换肤/圆角/渐变/阴影；
2. **qfluentwidgets**（zhiyiYo，支持 PySide6）：直接给 WinUI3 风格 Fluent 控件，翻新收益最大——⚠️ 社区版 GPLv3，闭源商用需购授权或照规范用 QSS 自撸；
3. **QML/QtQuick**：强动画需求终局方案，但新增技术栈。

对开发者工具（表格/表单/日志面板）的审美需求，前两档足够；除非产品媒体化（Notion 级设计稿还原），UI 上限不是瓶颈。

### 4.3 按「核心业务 + 桌宠」逐栈评估

| 栈 | 核心业务适配 | 桌宠适配 | 综合坑 |
|---|---|---|---|
| **PySide6** | 同进程直调，零 IPC | live2d-py 或帧动画；透明置顶原生 | 审美要抬；Live2D 依赖社区库 |
| **Electron** | Python sidecar + HTTP IPC（已有 APP_SERVER 可对接）；双运行时 | **最强**：Web Live2D 成熟；`setIgnoreMouseEvents(forward)` + hover 穿透成熟 | 内存体积重；双运行时调试 |
| **Tauri** | 同上 + Rust 侧管理 Python 子进程 | Web Live2D；`set_ignore_cursor_events` | 要养 Rust 技能点；WebView2 版本差异 |
| **WPF/WinUI3** | sidecar + IPC，对核心零加成 | VPet 证明帧动画可行；Live2D 走 WebView2/DirectX 别扭 | 双语言项目 |
| **Flutter Desktop** | sidecar + IPC | `window_manager` 做置顶/透明，穿透需自写平台通道 | 桌面端边角全靠社区补丁 |

**关键判断**：换栈唯一买到的是 UI 表现力，代价是「GUI ↔ 服务控制」从函数调用降级为跨进程 IPC——现一行 `server_button_click()` 解决的事，在 Electron 里要变成「渲染进程 → Node → HTTP → Python → 状态回传」全链路，连按钮中间态都需重设计。核心业务是重逻辑/重状态机的工具型面板，恰是 Qt Widgets 舒适区，非 Web 栈差异化优势区。

## 5. 结论

1. **不换栈。** 核心业务区 PySide6「同进程直控」优势换栈买不回；桌宠是唯一 Web 栈明显更爽的点，但 Qt 内经 live2d-py/帧动画可达 80 分——为一个装饰性功能换栈代价远大于踩坑成本；
2. **UI 翻新路线**：qfluentwidgets（先核授权）→ QSS 自绘 → 极端需求局部 QML；
3. **桌宠落地路径**：Spike（半天，验证四件事）→ V1 帧动画悬浮窗（交互先上线）→ V2 换 live2d-py，卡住则留帧动画，功能体验无损；
4. **新项目选型矩阵**（参考）：纯 Python 后端+工具面板 → PySide6；内容为王（IM/笔记/媒体/强设计稿）→ Electron/Tauri；Windows-only+极致 Fluent+团队会 C# → WinUI3/WPF；嵌入式/像素级一致 → Flutter/Slint；核心仍是 Python 中间件 → GUI 语言跟核心语言走，答案不变。

## 6. 待验证清单（Spike 项）

- [ ] `WA_TranslucentBackground` + `QOpenGLWidget` + live2d-py：透明背景是否生效
- [ ] 逐像素点击命中在叠 GL 部件后是否保留
- [ ] 与 `--in-process-gpu`（QTBUG-142355 workaround）共存
- [ ] PyInstaller 打入 Cubism Core DLL + 模型资源后正常运行

## 7. 关联文档

- [PRODUCT_DIRECTION_DISCUSSION](PRODUCT_DIRECTION_DISCUSSION.md) —— 产品定位与迭代方向
- [../reference/QT_BRIDGE.md](../reference/QT_BRIDGE.md) —— Qt Bridge 桥接协议分层说明
