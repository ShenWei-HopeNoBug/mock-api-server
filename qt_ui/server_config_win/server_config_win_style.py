# -*- coding: utf-8 -*-
window = '''
  #Dialog
  {
    background-color:rgb(255, 224, 178);
  }

  #confirmPushButton
  {
    background-color:rgb(250, 250, 250);
    border-radius:6px;
    border:1px solid skyblue;
    padding:4px 8px;
  }

  #confirmPushButton:hover
  {
    color:white;
    background-color:rgb(97, 97, 97);
    border-width:0;
  }

  #confirmPushButton:disabled
  {
    border:none;
  }

  QComboBox
  {
    background-color:rgb(250, 250, 250);
    border-radius:6px;
    border:1px solid skyblue;
    padding:4px 8px;
    min-height:24px;
  }

  QComboBox:hover
  {
    border:1px solid rgb(97, 97, 97);
  }

  QComboBox::drop-down
  {
    border:none;
    width:24px;
  }

  QComboBox::down-arrow
  {
    width:10px;
    height:10px;
  }

  /* 下拉列表样式由 QListView.setStyleSheet 单独控制，避免与自定义视图冲突 */'''
