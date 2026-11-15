# 主题色板单源化方案

> 状态：已实施
> 范围：`config/theme.py`（新增）/ `qt_ui/common_style.py` / `qt_ui/main_win/main_win_style.py` / `qt_win/app.py` / `qt_win/pet_shell.py` / `qt_win/server_config_dialog.py` / `qt_win/about_dialog.py` / `qt_win/desktop_pet.py` / `lib/splash.py` / `lib/webview_lib.py` / `tests/config/test_theme.py`（新增）

## 1. 背景

暖调配色已统一但色值仍散落硬编码，全项目 `rgb()/rgba()/QColor` 字面量约 130 处：

- `qt_ui/common_style.py` 39 处、`qt_ui/main_win/main_win_style.py` 38 处
- 内联 QSS 五处：`app.py` 退出蒙层、`splash.py` 启动卡（与蒙层逐字重复两份）、`server_config_dialog.py` QListView、`pet_shell.py` `PET_MENU_STYLE`、`about_dialog.py` LinkLabel
- `QColor` 字面量：pet 菜单图标与状态点、强制退出红、`desktop_pet` 降级球、`webview_lib` loading 灰系

后果：调色多点同步易漏（上轮 dialog 复选框回落原生即同类病）、splash/蒙层卡片样式复制漂移、QSS 色值与 QColor 两套写法无共同源。

## 2. 方案：`config/theme.py` 调色板 + Template 渲染

### 2.1 色值单源（落 config 而非 qt_ui）

- `config/theme.py`：`PALETTE` 字典 `名称 -> (r, g, b[, a])` 元组，暖调主板 + 中性灰分区（pet 菜单灰系、webview loading）
- 三个出口：
  - `c(name)` → `'rgb(r, g, b)'` / `'rgba(r, g, b, a)'` 字面量（QSS 用）
  - `qc(name)` → `QColor`（函数体 lazy import，保持 config 模块级无 PySide6 依赖，server 侧 config import 链不受累）
  - `qss(tpl)` → `string.Template(tpl).substitute()`，`$TOKEN` 占位渲染
- 选 `string.Template` 而非 f-string：QSS 满篇 `{}`，f-string 需 brace 翻倍；`$` 与 QSS 语法零冲突
- `white`/`transparent`/`none` 等 QSS 关键字保留字面，不进色板

### 2.2 QSS 片段 `$TOKEN` 化

- `common_style.py` / `main_win_style.py` 全部 `rgb()/rgba()` → `$TOKEN`，**import 时渲染**，导出仍是纯 `str`
- 14 个 `setStyleSheet(*_style.window)` 调用点零改动
- `button_group()` 保留 f-string 拼选择器（结构层），颜色走 `$TOKEN` 经 `qss()` 渲染

### 2.3 内联 QSS 迁移

- `common_style` 新增共享片段：`CARD_PANEL`（splash/退出蒙层共用卡片，含 `min-width:280px`）、`TIP_LABEL`、`PROGRESS_BAR`、`OVERLAY`（蒙层压暗）、`COMBO_DROP_VIEW`（server_config QListView 迁入）
- `pet_shell.PET_MENU_STYLE` 就地 `$TOKEN` 化（pet 专属灰系菜单不挪窝）
- `about_dialog` LinkLabel 改 `qss('color:$LINK')`
- `lib/splash.py` → `qt_ui.common_style` 引入依赖：lib→qt_ui 方向单向无环（common_style 不反向依赖）

### 2.4 QColor 调用点归拢

- `app.py`：状态点 `STATUS_ON/STATUS_WAIT/STATUS_OFF`、强制退出 `ICON_DANGER`
- `pet_shell.py`：图标默认 `HOVER_BG`/`WHITE`；`desktop_pet.py`：`PET_BALL`
- `webview_lib.py`：`SPINNER`/`SPINNER_TRACK`/`LOADING_BG`/`TEXT_MUTED`

### 2.5 不动项

- `win_ui.py` 生成物（红线）、`live2d_pet` 调试红框（dev-only）、webview 弹窗 HTML/JS 侧（超出 Qt QSS 射程）

## 3. 影响面

- 渲染产出与现状逐字节一致（golden master 验收）
- 调色仍需重启应用生效——与现状相同（本就是 import 时求值），不构成回退
- 依赖方向：`qt_ui/*` → `config.theme`；`lib/splash` → `qt_ui.common_style`；`lib/webview_lib`、`qt_win/*` → `config.theme`，无环

## 4. 验收

- golden master：重构前后全部 `*_style.window/tooltip` + `PET_MENU_STYLE` dump 逐字节 diff 为空
- `tests/config/test_theme.py`：PALETTE 值域合法、`c()/qss()` 渲染正确、未知 token 抛错、导出片段无 `$` 残留
- `ruff` 归零；全项目手码 `rgb(` 字面量清零（生成物/调试色除外）

## 5. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-14 | `config/theme.py` 调色板落地 | `PALETTE` 41 token（暖调 36 + 中性灰 5，按用途分注释）；`c()/qc()/qss()` 三出口，`qc()` 函数体 lazy import QColor 保 config 无 Qt 依赖 | `qc()` 返回注解走 `TYPE_CHECKING` 守卫过 ruff F821 |
| 2026-11-14 | 两样式文件 `$TOKEN` 化 | `common_style.py`/`main_win_style.py` 全量 `rgb()→$TOKEN`；golden master 重构前后 dump 逐字节一致；14 个 `setStyleSheet(*_style.window)` 调用点零改动 | `white`/`transparent` 等 QSS 关键字保留字面不进色板 |
| 2026-11-14 | 内联 QSS 迁移 + QColor 归拢 | common_style 新增 `CARD_PANEL`/`TIP_LABEL`/`PROGRESS_BAR`/`OVERLAY`/`COMBO_DROP_VIEW` 五片段；app.py 蒙层+splash 卡片同源化消除逐字重复；QColor 字面量 10 处归 `qc()` | splash 卡片顺带获得蒙层同款 `min-width:280px`（SPLASH_WIDTH=360 容纳无影响） |
| 2026-11-14 | 测试与验证 | 新增 `tests/config/test_theme.py` 8 例（值域/`c()`/`qss()`/未知 token 抛错/片段无 `$` 残留）；全量 pytest 通过；ruff 归零；手码 `rgb(` 字面量仅剩 live2d 调试红框 | golden master 比对为最强保证：渲染结果与改前逐字节一致 |
| 2026-11-15 | webview loading 暖调化 | `SPINNER`/`SPINNER_TRACK`/`LOADING_BG`/`TEXT_MUTED` 四 token 由中性灰改暖调值（分别对齐 ACCENT/PROGRESS_BG/WINDOW_BG/DISABLED_TEXT）并移出中性灰区（仅留 pet 菜单 GRAY_*）；两 webview 弹窗 `setBackgroundColor(Qt.white)` → `qc('WINDOW_BG')` | loading 灰白与暖调主题不搭；underlay 白底属前端页面暖调化后漏改（注释原意即「底色与页面一致」，页面 :root 已是 `#ffe8c3`） |

## 6. 方案修正

| 日期 | 原方案 | 实际做法 | 原因 |
|---|---|---|---|
| 2026-11-14 | 调色板落 `qt_ui/theme.py` | 落 `config/theme.py` | 用户拍板：config 本为纯常量层，palette 无 Qt 依赖更干净，`lib/` 侧引用也不产生 lib→qt_ui 依赖 |
| 2026-11-14 | `qc()` 模块级 `from PySide6.QtGui import QColor` | 函数体 lazy import + `TYPE_CHECKING` 注解 | 保持 config 模块级无 PySide6 依赖：server 侧（mitmproxy 子进程等）import config 链不引入 Qt 包 |
