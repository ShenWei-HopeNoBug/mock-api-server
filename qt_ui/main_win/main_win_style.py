# -*- coding: utf-8 -*-
window = '''
  #MainWindow{
    background-color:rgb(255, 232, 195);
  }

  QMenuBar{
    background-color:rgb(255, 248, 225);
  }

  QMenuBar::item {
    padding:3px 8px;
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

  QMenu{
    background-color:rgb(255, 248, 225);
  }

  QMenu::item{
    padding: 4px 20px;
    border-radius:4px;
  }

  QMenu::item:selected{
    color:white;
    background-color:rgb(97, 97, 97);
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

  QCheckBox{
    color:rgb(96, 62, 30);
  }

  QCheckBox::indicator{
    width:14px;
    height:14px;
    border-radius:3px;
    border:1px solid rgba(150, 110, 60, 110);
    background-color:rgb(255, 248, 225);
  }

  QCheckBox::indicator:checked{
    background-color:rgb(205, 140, 65);
    border:1px solid rgb(165, 105, 45);
  }
'''
