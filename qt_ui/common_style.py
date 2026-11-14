# -*- coding: utf-8 -*-
# 全应用共享暖调 QSS 片段（与 main_win_style 同源色板）
# 各 *_win_style.py / module_style.py 组合引用，统一调色只改此处，不再逐文件复制色值

# 对话框大底（与主面板同色）+ 全局文字暖深棕
DIALOG_BASE = '''
  #Dialog{
    background-color:rgb(255, 232, 195);
  }

  QLabel{
    color:rgb(96, 62, 30);
  }
'''

# 模块内文字色（QWidget 模块非 Dialog，只补文字，不动底色）
MODULE_TEXT = '''
  QLabel{
    color:rgb(96, 62, 30);
  }
'''

# 按钮组三态样式生成：QSS 逗号选择器组的伪类需逐名展开（#a,#b:hover 只命中 #b 的 hover）
def button_group(*names: str) -> str:
  normal = ',\n  '.join(names)
  hover = ',\n  '.join(f'{n}:hover' for n in names)
  disabled = ',\n  '.join(f'{n}:disabled' for n in names)
  return f'''
  {normal}
  {{
    color:rgb(96, 62, 30);
    background-color:rgb(255, 252, 246);
    border-radius:6px;
    border:1px solid rgb(195, 148, 95);
    padding:4px 8px;
  }}

  {hover}
  {{
    color:white;
    background-color:rgb(97, 97, 97);
    border-width:0;
  }}

  {disabled}
  {{
    color:rgb(165, 140, 115);
    border:1px solid rgb(215, 190, 160);
    background-color:rgb(250, 242, 228);
  }}
'''

# 文本输入框（含 focus 强调态）
LINE_EDIT = '''
  QLineEdit{
    color:rgb(96, 62, 30);
    background-color:rgb(255, 248, 225);
    border-radius:6px;
    border:1px solid rgba(160, 120, 70, 70);
    padding:2px 8px;
  }

  QLineEdit:focus{
    border:1px solid rgb(190, 140, 80);
  }
'''

SPIN_BOX = '''
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
'''

# 复选框：文字暖深棕 + 暖色指示框，选中态暖橙填充
CHECK_BOX = '''
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

TEXT_EDIT = '''
  QTextEdit{
    color:rgb(96, 62, 30);
    border-radius:6px;
    background-color:rgb(255, 248, 225);
    border:1px solid rgba(160, 120, 70, 70);
    padding:4px;
  }

  QTextEdit:focus{
    border:1px solid rgb(190, 140, 80);
  }
'''

# 下拉框：drop-down/down-arrow 结构保留（原为 skyblue 描边），换暖棕边 + focus 态
COMBO_BOX = '''
  QComboBox
  {
    color:rgb(96, 62, 30);
    background-color:rgb(255, 252, 246);
    border-radius:6px;
    border:1px solid rgb(195, 148, 95);
    padding:4px 8px;
    min-height:24px;
  }

  QComboBox:hover
  {
    border:1px solid rgb(190, 140, 80);
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
'''

# 列表控件：item 暖深棕字 + 暖棕下划线提示，选中态暖橙强调
LIST_WIDGET = '''
  QListWidget{
    border-radius:6px;
    background-color:rgb(255, 248, 225);
    border:1px solid rgba(160, 120, 70, 70);
  }

  QListWidget::item{
    background-color:transparent;
    color:rgb(96, 62, 30);
    border-radius:4px;
    padding:0 2px;
  }

  QListWidget::item:hover{
    border-bottom:1px solid rgb(190, 140, 80);
  }

  QListWidget::item:selected{
    border-bottom:1px solid rgb(190, 140, 80);
    color:rgb(210, 110, 45);
  }
'''

# 滚动条：灰色 handle 换淡暖棕（结构沿用原有 6px 细条方案）
SCROLLBAR = '''
  QScrollBar:vertical {
    border: none;
    background: none;
    width: 6px;
    margin: 0px;
  }

  QScrollBar::handle:vertical {
    background: rgb(205, 170, 125);
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
    background: rgb(205, 170, 125);
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
'''
