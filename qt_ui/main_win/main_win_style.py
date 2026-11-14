# -*- coding: utf-8 -*-
from config.theme import qss
from qt_ui.common_style import CHECK_BOX

# 全局 tooltip 样式：tooltip 是 Qt 自建顶层窗，须挂 QApplication 级才生效（main.py setStyleSheet）
tooltip = qss('''
  /* 不加 border-radius：Windows 下 QToolTip 为不透明顶层窗，圆角外会露原生矩形底色 */
  QToolTip {
    color:$TEXT;
    background-color:$PANEL_BG;
    border:1px solid $BORDER;
    padding:6px 10px;
    font-size:12px;
  }
''')

window = qss('''
  #MainWindow{
    background-color:$WINDOW_BG;
  }

  QMenuBar{
    background-color:$PANEL_BG;
    border-bottom:1px solid $HAIRLINE;
  }

  QMenuBar::item {
    color:$TEXT;
    padding:4px 10px;
    border-radius:4px;
  }

  QMenuBar::item:selected {
    border:none;
    color:white;
    background-color:$HOVER_BG;
  }

  QMenuBar::item:disabled {
    color:$MENU_DISABLED;
  }

  QMenuBar::item:disabled:selected {
    color:$MENU_DISABLED;
    background-color:transparent;
  }

  /* 不加 border-radius：QMenu 下拉为顶层弹窗，圆角外会露原生矩形底色（同 tooltip 坑位） */
  QMenu{
    background-color:$PANEL_BG;
    border:1px solid $MENU_BORDER;
    padding:4px;
  }

  QMenu::item{
    color:$TEXT;
    padding: 4px 20px;
    border-radius:4px;
  }

  QMenu::item:selected{
    color:white;
    background-color:$HOVER_BG;
  }

  QMenu::separator{
    height:1px;
    background:$HAIRLINE;
    margin:3px 8px;
  }

  QMenu::item:disabled {
    color:$MENU_DISABLED;
  }

  QMenu::item:disabled:selected {
    color:$MENU_DISABLED;
    background-color:transparent;
  }

  /* 全局文字：暖深棕，与烤色底协调 */
  QLabel{
    color:$TEXT;
  }

  /* 分区卡片：浅色底 + 圆角 + 细描边，承载一个配置分区 */
  #cardServer, #cardCatch, #cardMcp{
    background-color:$CARD_BG;
    border-radius:10px;
    border:1px solid $CARD_BORDER;
  }

  /* 卡内分隔线：1px 暖棕细线，与标题分隔线同色系 */
  #serverDivider{
    color:$TITLE;
    background-color:$DIVIDER;
    max-height:1px;
    border:none;
  }

  /* 分区标题：加粗 + 底部细分隔线，建立视觉层级（替代原文本【】括号） */
  #label_4, #label_5, #label_mcp{
    font-size:14px;
    font-weight:bold;
    color:$TITLE;
    border-bottom:1px solid $TITLE_LINE;
    padding-bottom:3px;
  }

  QLineEdit{
    background-color:$PANEL_BG;
    border-radius:6px;
    border:1px solid $BORDER_SOFT;
    padding:2px 8px;
  }

  QLineEdit:focus{
    border:1px solid $BORDER_FOCUS;
  }

  #catchServerButton,
  #staticDownloadButton,
  #serverButton,
  #mcpServerButton
  {
    color:$TEXT;
    background-color:$BTN_BG;
    border-radius:6px;
    border:1px solid $BORDER;
    padding:4px 8px;
    min-width:110px;
  }

  #catchServerButton:hover,
  #staticDownloadButton:hover,
  #serverButton:hover,
  #mcpServerButton:hover
  {
    color:white;
    background-color:$HOVER_BG;
    border-width:0;
  }

  #catchServerButton:disabled,
  #staticDownloadButton:disabled,
  #serverButton:disabled,
  #mcpServerButton:disabled
  {
    color:$DISABLED_TEXT;
    border:1px solid $DISABLED_BORDER;
    background-color:$DISABLED_BG;
  }

  QSpinBox{
    color:$TEXT;
    background-color:$PANEL_BG;
    border-radius:4px;
    border:1px solid $BORDER_SOFT;
    padding:4px;
  }

  QSpinBox:focus{
    border:1px solid $BORDER_FOCUS;
  }
''') + CHECK_BOX
