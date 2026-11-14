# 主面板暖调美化与布局重排方案

> 状态：已实施
> 范围：`qt_ui/main_win/win_ui.ui` / `qt_ui/main_win/main_win_style.py` / `qt_ui/main_win/win_ui.py`（生成物）/ `qt_win/app.py`

## 1. 背景

主面板两大问题：

- **结构**：`win_ui.ui` 全部控件绝对定位（`geometry` 坐标），无布局管理——行列对不齐、间距靠手感、窗口尺寸变化不自适应；且根部件声明 `QWidget` 与实际 `QMainWindow` 类型不符（靠绝对定位掩盖）
- **视觉**：分区标题用文本【】括号假装层级；按钮 `skyblue` 冷描边与暖橙底冲突；输入框无边框在浅底上辨识弱；复选框默认蓝色不协调

## 2. 方案：两档递进

### 档 A：纯样式美化（commit `0528c52`）

不改 `.ui`，只改 `main_win_style.py`：

| 项 | 改动 |
|---|---|
| 分区标题 | `#label_4/#label_5/#label_mcp`：14px 加粗 + 深棕 `rgb(122,76,36)` + 底部半透明分隔线（括号由 `app.py` setText 去除） |
| 全局文字 | QLabel/SpinBox/CheckBox：黑 → 暖深棕 `rgb(96,62,30)` |
| 按钮 | `skyblue` 描边 → 暖棕 `rgb(195,148,95)`，底色暖白 `rgb(255,252,246)`；补 disabled 三态 |
| 输入框 | 加 `rgba(160,120,70,70)` 描边 + focus 加深 `rgb(190,140,80)` |
| 复选框 | indicator 奶白底暖棕描边，选中实心 `rgb(205,140,65)` |
| 大底 | 用户定调微提亮：`255,224,178` → `255,232,195` |

### 档 B：结构重排（本 commit）

- `.ui` 根部件 `QWidget` → `QMainWindow`（修正类型声明）+ 标准 `centralwidget` 承载 `QVBoxLayout`
- 三配置区改 `QFrame` 卡片（`cardServer/cardCatch/cardMcp`），顺序调整：**服务配置 → 抓包配置 → MCP 配置**（主服务在前，与服务依赖矩阵一致）
- 卡片样式：浅奶底 `rgba(255,250,238,150)` + 圆角 10px + 细暖棕描边
- 三个端口输入框同一 x 位对齐；启动按钮统一右对齐 + `min-width:110px`（防启动/停止文案切换撑缩）
- 复选框收进服务配置卡不再悬空；"静态资源下载"与速率同行右对齐
- `.ui` 标题文本直接写净文案（服务配置/抓包配置/MCP 配置），档 A 的 setText 去除
- 窗口 619×460 → 619×476；全部 objectName 保留，零业务逻辑改动

## 3. 影响面

- `win_ui.py` 为 `pyside6-uic` 生成物，改动只走 `.ui`（红线合规）
- `app.py` 引用 objectName 全部保留：`setupUi` 后控件树结构变化（父节点 MainWindow→centralwidget）但引用方式不变；`setFixedSize` 仍生效
- `menuBar()` 由 QMainWindow 懒创建不受影响；QSS `#MainWindow` objectName 选择器仍命中

## 4. 验收

- 离屏 `setupUi` 验证：三端口框 x=74 对齐，三卡纵向排布
- 真机：卡片底/间距协调，按钮宽度统一不抖动，启动/停止切换无布局跳动
- `ruff` 归零

## 5. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-14 | 档 A 样式美化 | commit `0528c52`：标题层级/暖棕配色/描边/复选框/底色提亮 | 用户两轮调色后定稿 |
| 2026-11-14 | 档 B 布局重排 | `.ui` 全量重写为 QVBoxLayout+三卡片；根部件类型修正 QMainWindow；按钮 min-width 110px；`win_ui.py` 重新生成 | 首次生成后布局塌缩——QMainWindow setLayout 被拒，修正根部件类型后正常 |

## 6. 方案修正

| 日期 | 原方案 | 实际做法 | 原因 |
|---|---|---|---|
| 2026-11-14 | `.ui` 根部件沿用 `QWidget` 直接挂 QVBoxLayout | 根部件改 `QMainWindow` + `centralwidget` 承载布局 | `QMainWindow` 自带内部布局，`setLayout` 静默失败导致控件全部塌缩到原点；原 `.ui` 的 QWidget 声明本身即类型错误，被绝对定位掩盖 |
| 2026-11-14 | 档 A 中 setText 去【】 | 档 B 中 `.ui` 直接写净文案，setText 删除 | 布局重写后 `.ui` 即为单一事实源，代码无需二次修正 |
