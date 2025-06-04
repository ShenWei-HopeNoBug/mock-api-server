# -*- coding: utf-8 -*-
window = '''
  #Dialog{
    background-color:rgb(255, 224, 178);
  }
  
  QTextEdit{
    border-radius:6px;
    background-color:rgb(255, 248, 225);
    border:none;
    padding:4px;
  }
  
  #confirmPushButton
  {
    background-color:rgb(250, 250, 250);
    border-radius:6px;
    border:1px solid skyblue;
    padding:4px 8px;
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
'''
