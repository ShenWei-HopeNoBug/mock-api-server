# -*- coding: utf-8 -*-
from qt_ui.common_style import CHECK_BOX

# 全局 tooltip 样式：tooltip 是 Qt 自建顶层窗，须挂 QApplication 级才生效（main.py setStyleSheet）
tooltip = '''
  /* 不加 border-radius：Windows 下 QToolTip 为不透明顶层窗，圆角外会露原生矩形底色 */
  QToolTip {
    color:rgb(96, 62, 30);
    background-color:rgb(255, 248, 225);
    border:1px solid rgb(195, 148, 95);
    padding:6px 10px;
    font-size:12px;
  }
'''

window = '''
  #MainWindow{
    background-color:rgb(255, 232, 195);
  }

  QMenuBar{
    background-color:rgb(255, 248, 225);
    border-bottom:1px solid rgba(150, 110, 60, 50);
  }

  QMenuBar::item {
    color:rgb(96, 62, 30);
    padding:4px 10px;
    border-radius:4px;
  }

  QMenuBar::item:selected {
    border:none;
    color:white;
    background-color:rgb(97, 97, 97);
  }

  QMenuBar::item:disabled {
    color:rgb(160, 160, 160);
  }

  QMenuBar::item:disabled:selected {
    color:rgb(160, 160, 160);
    background-color:transparent;
  }

  /* 不加 border-radius：QMenu 下拉为顶层弹窗，圆角外会露原生矩形底色（同 tooltip 坑位） */
  QMenu{
    background-color:rgb(255, 248, 225);
    border:1px solid rgba(150, 110, 60, 60);
    padding:4px;
  }

  QMenu::item{
    color:rgb(96, 62, 30);
    padding: 4px 20px;
    border-radius:4px;
  }

  QMenu::item:selected{
    color:white;
    background-color:rgb(97, 97, 97);
  }

  QMenu::separator{
    height:1px;
    background:rgba(150, 110, 60, 50);
    margin:3px 8px;
  }

  QMenu::item:disabled {
    color:rgb(160, 160, 160);
  }

  QMenu::item:disabled:selected {
    color:rgb(160, 160, 160);
    background-color:transparent;
  }

  /* 全局文字：暖深棕，与烤色底协调 */
  QLabel{
    color:rgb(96, 62, 30);
  }

  /* 分区卡片：浅色底 + 圆角 + 细描边，承载一个配置分区 */
  #cardServer, #cardCatch, #cardMcp{
    background-color:rgba(255, 250, 238, 150);
    border-radius:10px;
    border:1px solid rgba(150, 110, 60, 45);
  }

  /* 卡内分隔线：1px 暖棕细线，与标题分隔线同色系 */
  #serverDivider{
    color:rgb(122, 76, 36);
    background-color:rgba(122, 76, 36, 50);
    max-height:1px;
    border:none;
  }

  /* 分区标题：加粗 + 底部细分隔线，建立视觉层级（替代原文本【】括号） */
  #label_4, #label_5, #label_mcp{
    font-size:14px;
    font-weight:bold;
    color:rgb(122, 76, 36);
    border-bottom:1px solid rgba(122, 76, 36, 70);
    padding-bottom:3px;
  }

  QLineEdit{
    background-color:rgb(255, 248, 225);
    border-radius:6px;
    border:1px solid rgba(160, 120, 70, 70);
    padding:2px 8px;
  }

  QLineEdit:focus{
    border:1px solid rgb(190, 140, 80);
  }

  #catchServerButton,
  #staticDownloadButton,
  #serverButton,
  #mcpServerButton
  {
    color:rgb(96, 62, 30);
    background-color:rgb(255, 252, 246);
    border-radius:6px;
    border:1px solid rgb(195, 148, 95);
    padding:4px 8px;
    min-width:110px;
  }

  #catchServerButton:hover,
  #staticDownloadButton:hover,
  #serverButton:hover,
  #mcpServerButton:hover
  {
    color:white;
    background-color:rgb(97, 97, 97);
    border-width:0;
  }

  #catchServerButton:disabled,
  #staticDownloadButton:disabled,
  #serverButton:disabled,
  #mcpServerButton:disabled
  {
    color:rgb(165, 140, 115);
    border:1px solid rgb(215, 190, 160);
    background-color:rgb(250, 242, 228);
  }

  QSpinBox{
    color:rgb(96, 62, 30);
    background-color:rgb(255, 248, 225);
    border-radius:4px;
    border:1px solid rgba(160, 120, 70, 70);
    padding:4px;
  }

  QSpinBox:focus{
    border:1px solid rgb(190, 140, 80);
  }
''' + CHECK_BOX
