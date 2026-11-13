# 桌宠右键菜单服务快捷操作方案

> 状态：已实施
> 关联：[desktop-pet-basic-plan](desktop-pet-basic-plan.md) / [desktop-pet-live2d-plan](desktop-pet-live2d-plan.md)

## 1. 背景与目标

桌宠模式下服务启停仍需回主面板操作。本方案把三个服务的启动/停止快捷项加入桌宠右键菜单，并完整复刻主面板的跨服务禁用关系。

## 2. 现状：三服务与禁用矩阵

| 服务 | 状态字段 | 切换方法 | 按钮文本 |
|---|---|---|---|
| mock 服务 | `server_status` | `server_button_click()` | 启动服务/停止服务 |
| 抓包服务 | `mitmproxy_server_status` | `catch_server_button_click()` | 启动抓包服务/停止抓包服务 |
| MCP 服务 | `mcp_server_status` | `mcp_server_button_click()` | 启动MCP服务/停止MCP服务 |

状态统一为 `READY` / `START_WAIT` / `RUNNING` / `STOP_WAIT`。

**跨服务禁用矩阵**（从 `server_status_change` / `mitmproxy_server_status_change` / `mcp_server_status_change` 提取）：

| 谁 != READY | 禁用了谁 |
|---|---|
| 抓包 | mock + MCP |
| mock | 抓包 |
| MCP | 抓包 |

可启动条件：抓包需 mock、MCP 全停（最重依赖）；mock、MCP 各只需抓包停；mock 与 MCP 互不排斥可同时运行。自身过渡态（START_WAIT/STOP_WAIT）一律禁用。

## 3. 菜单结构

```
● 启动服务
● 启动抓包服务
● 启动MCP服务
─────────────
▭ 打开主面板
⏻ 退出
```

- 服务项图标为状态点：灰 `rgb(150,150,150)`=未运行 / 绿 `rgb(90,170,90)`=运行中 / 橙 `rgb(230,160,60)`=过渡中
- 标签随状态：READY→「启动xx」、RUNNING→「停止xx」、过渡态→「正在启动...」/「正在停止...」
- 菜单每次右键重建，读取当下状态字段，无需订阅状态变化

## 4. 架构：菜单构建钩子注入

`PetShellMixin._init_pet_shell` 加可选回调 `on_build_menu: Callable[[QMenu], None]`；`contextMenuEvent` 顺序：钩子（注入服务项）→ `addSeparator` → 原有「打开主面板/退出」。mixin 不感知"服务"概念，壳层保持纯净。

`MainWindow` 新增 `_build_pet_service_menu(menu)`：遍历三服务，读状态 → 算标签 + 可用性 → `addAction(图标, 标签)` + `setEnabled` + `triggered` **复用现有 `*_button_click()`**，服务启停逻辑零改动。

禁用判定 `_pet_service_enabled(name)`：自身过渡态 False；跨服务按矩阵——catch 需 mock==READY 且 mcp==READY，mock/MCP 需 catch==READY。

**已知边界**：`*_button_click` 只查自身过渡态，跨服务禁用仅靠按钮 `setDisabled` 一道闸——pet 菜单禁用算错即绕过该闸（如抓包运行时点到"启动服务"）。矩阵实现是重点，须与状态处理器保持同步（注释标注双写点）。

## 5. 改动清单

| 文件 | 改动 |
|---|---|
| `qt_win/pet_shell.py` | `_init_pet_shell` +`on_build_menu=None`；`contextMenuEvent` 顺序调整；`PET_MENU_STYLE` 补 `QMenu::separator`；`_draw_icon_pixmap` +`dot` kind |
| `qt_win/app.py` | `_create_pet` 传钩子；+`_build_pet_service_menu`/`_pet_service_enabled` |

球版/Live2D 版共用 mixin，同时获得服务菜单；主面板按钮与启停实现零改动。

## 6. 验收矩阵

| 场景 | 预期 |
|---|---|
| 全 READY | 三项可点；点"启动抓包"→ 抓包起，mock/MCP 项下次开菜单变灰 |
| 抓包 RUNNING | mock/MCP 置灰，抓包显示"停止抓包服务"可点 |
| mock RUNNING | 抓包置灰，MCP 仍可点 |
| MCP RUNNING | 抓包置灰，mock 仍可点 |
| mock+MCP 同 RUNNING | 抓包置灰 |
| 任一过渡态 | 该项"正在启动/停止..."置灰 |
| 菜单退出/打开主面板 | 无回归 |

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-14 | 全量实施 | `pet_shell.py`：`on_build_menu` 钩子 + `make_pet_menu_icon` 公开入口（`_make_menu_icon` 重命名导出）+ `dot` kind + `QMenu::separator` 样式；`app.py`：`_build_pet_service_menu`/`_pet_service_enabled` + 三处构造点接线 | ruff 归零；离屏验证：dot 图标按色渲染、禁用矩阵 6 场景全对（全 READY/抓包 RUNNING/mock RUNNING/MCP RUNNING/mock+MCP 双 RUNNING/过渡态） |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| 2026-11-14 | `Live2DPetWindow`/`DesktopPetWindow` 的 `__init__` 补 `on_build_menu` 参数透传至 `_init_pet_shell` | 初版只改了 mixin 签名未透传：`Live2DPetWindow` 收未知参数 TypeError → 被降级逻辑捕获 → `DesktopPetWindow` 同样 TypeError → 无兜底直接闪退 |
