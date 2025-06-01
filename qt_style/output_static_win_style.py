# -*- coding: utf-8 -*-
window='''
  #Dialog{
    background-color:rgb(255, 224, 178);
  }
  
  QLineEdit{
    background-color:rgb(255, 248, 225);
    border-radius:8px;
    border:none;
    padding:2px 8px;
  }
  
  QListWidget{
    border-radius:8px;
    background-color:rgb(255, 248, 225);
    border:none;
    padding:0 4px;
  }
  
  QListWidget::item{
    background-color:transparent;
    color:rgb(121,112,52);
    border-radius:6px;
    padding:2px 0;
  }
  
  QListWidget::item:hover{
    border-bottom:1px solid rgb(121,112,52);
  }
  
  QListWidget::item:selected{
    border-bottom:1px solid rgb(121,112,52);
    color:rgb(255, 112, 67);
  }
  
  #browsePushButton,
  #clearPushButton,
  #addPushButton,
  #deletePushButton,
  #outputPushButton
  {
    background-color:rgb(250, 250, 250);
    border-radius:6px;
    border:1px solid skyblue;
    padding:4px 8px;
    cursor:pointer;
  }

  #browsePushButton:hover,
  #clearPushButton:hover,
  #addPushButton:hover,
  #deletePushButton:hover,
  #outputPushButton:hover
  {
    color:white;
    background-color:rgb(97, 97, 97);
    border-width:0;
  }

  #browsePushButton:disabled,
  #clearPushButton:disabled,
  #addPushButton:disabled,
  #deletePushButton:disabled,
  #outputPushButton:disabled
  {
    border:none;
  }
'''