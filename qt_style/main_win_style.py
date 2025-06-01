# -*- coding: utf-8 -*-
window = '''
  #MainWindow{
    background-color:rgb(255, 224, 178);
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

  QLineEdit{
    background-color:rgb(255, 248, 225);
    border-radius:8px;
    border:none;
    padding:2px 8px;
  }

  #catchServerButton,
  #staticDownloadButton,
  #serverButton
  {
    background-color:rgb(250, 250, 250);
    border-radius:6px;
    border:1px solid skyblue;
    padding:4px 8px;
    cursor:pointer;
  }

  #catchServerButton:hover,
  #staticDownloadButton:hover,
  #serverButton:hover
  {
    color:white;
    background-color:rgb(97, 97, 97);
    border-width:0;
  }

  #catchServerButton:disabled,
  #staticDownloadButton:disabled,
  #serverButton:disabled
  {
    border:none;
  }

  QSpinBox{
    background-color:rgb(255, 248, 225);
    border-radius:4px;
    padding:4px;
  }
'''
