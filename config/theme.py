# -*- coding: utf-8 -*-
# 主题调色板：全部 UI 色值单源，QSS 字符串与 QColor 双出口
# 调色只改 PALETTE；QSS 片段以 $TOKEN 引用，经 qss() 渲染为 rgb()/rgba() 字面量
from string import Template
from typing import TYPE_CHECKING, Dict, Tuple

if TYPE_CHECKING:
  from PySide6.QtGui import QColor

# 值取 (r, g, b) 或 (r, g, b, a)，分量 0-255
PALETTE: Dict[str, Tuple[int, ...]] = {
  # ---- 暖调主色板 ----
  'WINDOW_BG': (255, 232, 195),         # 窗体大底
  'PANEL_BG': (255, 248, 225),          # 卡片/输入框/菜单/tooltip/复选框底
  'PANEL_HOVER': (255, 245, 225),       # 下拉列表项 hover 底
  'PANEL_SELECT': (255, 224, 178),      # 下拉列表项选中底
  'CARD_BG': (255, 250, 238, 150),      # 主面板分区卡片
  'CARD_BORDER': (150, 110, 60, 45),    # 分区卡片描边
  'TEXT': (96, 62, 30),                 # 主文字暖深棕
  'TITLE': (122, 76, 36),               # 分区标题
  'TITLE_LINE': (122, 76, 36, 70),      # 标题下分隔线
  'DIVIDER': (122, 76, 36, 50),         # 卡内分隔线
  'HAIRLINE': (150, 110, 60, 50),       # 菜单栏底边/菜单分隔线
  'MENU_BORDER': (150, 110, 60, 60),    # 菜单描边
  'BTN_BG': (255, 252, 246),            # 按钮底
  'BORDER': (195, 148, 95),             # 按钮/下拉/tooltip 描边
  'BORDER_SOFT': (160, 120, 70, 70),    # 输入框/列表描边
  'BORDER_FOCUS': (190, 140, 80),       # focus/hover 描边强调
  'INDICATOR_BORDER': (150, 110, 60, 110),  # 复选框指示框描边
  'HOVER_BG': (97, 97, 97),             # 深灰 hover（菜单选中/按钮 hover/pet 图标）
  'DISABLED_TEXT': (165, 140, 115),     # 按钮禁用文字
  'DISABLED_BORDER': (215, 190, 160),   # 按钮禁用描边
  'DISABLED_BG': (250, 242, 228),       # 按钮禁用底
  'MENU_DISABLED': (160, 160, 160),     # 菜单禁用文字
  'ACCENT': (205, 140, 65),             # 强调橙（复选框选中）
  'ACCENT_DEEP': (165, 105, 45),        # 强调橙描边
  'ACCENT_TEXT': (210, 110, 45),        # 列表选中文字橙
  'LINK': (190, 110, 40),               # 链接文字
  'PROGRESS_BG': (240, 222, 192),       # 进度条轨道
  'SCROLLBAR': (205, 170, 125),         # 滚动条 handle
  'OVERLAY_DIM': (0, 0, 0, 140),        # 退出蒙层压暗
  'ICON_DANGER': (200, 60, 60),         # 强制退出图标
  'STATUS_ON': (90, 170, 90),           # 服务运行状态点
  'STATUS_WAIT': (230, 160, 60),        # 服务过渡态状态点
  'STATUS_OFF': (150, 150, 150),        # 服务停止状态点
  'PET_BALL': (250, 140, 60),           # 降级桌宠占位球
  'WHITE': (255, 255, 255),             # 图标高亮（QSS 白字用 white 关键字，不走色板）

  # ---- webview loading（与暖调页面对齐，loading→页面切栈零色差）----
  'SPINNER': (205, 140, 65),            # loading 旋转弧（同 ACCENT）
  'SPINNER_TRACK': (240, 222, 192),     # loading 底环（同 PROGRESS_BG）
  'LOADING_BG': (255, 232, 195),        # webview 加载占位底（同 WINDOW_BG，与页面 :root 背景一致）
  'TEXT_MUTED': (165, 140, 115),        # webview 加载提示文字（同 DISABLED_TEXT）

  # ---- 中性灰（pet 菜单等非暖调场景）----
  'GRAY_TEXT': (80, 80, 80),            # pet 菜单项文字
  'GRAY_LINE': (97, 97, 97, 60),        # pet 菜单描边/分隔线
}


def c(name: str) -> str:
  """色值转 QSS 字面量：'rgb(r, g, b)' 或 'rgba(r, g, b, a)'"""
  v = PALETTE[name]
  if len(v) == 4:
    return f'rgba({v[0]}, {v[1]}, {v[2]}, {v[3]})'
  return f'rgb({v[0]}, {v[1]}, {v[2]})'


def qc(name: str) -> 'QColor':
  """色值转 QColor（lazy import：保持 config 模块级无 PySide6 依赖，server 侧 import 链不受累）"""
  from PySide6.QtGui import QColor
  return QColor(*PALETTE[name])


_CSS_VARS: Dict[str, str] = {name: c(name) for name in PALETTE}


def qss(template: str) -> str:
  """渲染 QSS 模板：$TOKEN 占位符替换为调色板字面量；未知 token 直接抛错防静默漏配"""
  return Template(template).substitute(_CSS_VARS)
