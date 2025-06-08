# -*- coding: utf-8 -*-
window = '''
  QListWidget{
    border-radius:6px;
    background-color:rgb(255, 248, 225);
    border:none;
  }

  QListWidget::item{
    background-color:transparent;
    color:rgb(121,112,52);
    border-radius:4px;
    padding:0 2px;
  }

  QListWidget::item:hover{
    border-bottom:1px solid rgb(121,112,52);
  }

  QListWidget::item:selected{
    border-bottom:1px solid rgb(121,112,52);
    color:rgb(255, 112, 67);
  }

  QScrollBar:vertical {
    border: none;
    background: none;
    width: 6px;
    margin: 0px;
  }

  QScrollBar::handle:vertical {
    background: grey;
    min-height: 20px;
    border-radius: 3px;
  }

  QScrollBar::add-line:vertical, 
  QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
    subcontrol-position: left;
  }

  QScrollBar::add-page:vertical, 
  QScrollBar::sub-page:vertical {
    background: none;
  }

  QScrollBar:horizontal {
    border: none;
    background: none;
    height: 6px;
    margin: 0px;
  }

  QScrollBar::handle:horizontal {
    background: grey;
    min-width: 20px;
    border-radius: 3px;
  }

  QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
    subcontrol-position: top;
  }

  QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
  }

  #clearPushButton,
  #addPushButton,
  #editPushButton,
  #deletePushButton
  {
    background-color:rgb(250, 250, 250);
    border-radius:6px;
    border:1px solid skyblue;
    padding:4px 8px;
  }

  #clearPushButton:hover,
  #addPushButton:hover,
  #editPushButton:hover,
  #deletePushButton:hover
  {
    color:white;
    background-color:rgb(97, 97, 97);
    border-width:0;
  }

  #clearPushButton:disabled,
  #addPushButton:disabled,
  #editPushButton:disabled,
  #deletePushButton:disabled
  {
    border:none;
  }
'''
