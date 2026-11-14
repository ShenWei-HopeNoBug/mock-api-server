# -*- coding: utf-8 -*-
# 全应用共享暖调 QSS 片段（色值经 config.theme 调色板 $TOKEN 渲染）
# 各 *_win_style.py / module_style.py 组合引用，统一调色只改 config/theme.py，不再逐文件复制色值
from config.theme import qss

# 对话框大底（与主面板同色）+ 全局文字暖深棕
DIALOG_BASE = qss('''
  #Dialog{
    background-color:$WINDOW_BG;
  }

  QLabel{
    color:$TEXT;
  }
''')

# 模块内文字色（QWidget 模块非 Dialog，只补文字，不动底色）
MODULE_TEXT = qss('''
  QLabel{
    color:$TEXT;
  }
''')

# 按钮组三态样式生成：QSS 逗号选择器组的伪类需逐名展开（#a,#b:hover 只命中 #b 的 hover）
def button_group(*names: str) -> str:
  normal = ',\n  '.join(names)
  hover = ',\n  '.join(f'{n}:hover' for n in names)
  disabled = ',\n  '.join(f'{n}:disabled' for n in names)
  return qss(f'''
  {normal}
  {{
    color:$TEXT;
    background-color:$BTN_BG;
    border-radius:6px;
    border:1px solid $BORDER;
    padding:4px 8px;
  }}

  {hover}
  {{
    color:white;
    background-color:$HOVER_BG;
    border-width:0;
  }}

  {disabled}
  {{
    color:$DISABLED_TEXT;
    border:1px solid $DISABLED_BORDER;
    background-color:$DISABLED_BG;
  }}
''')

# 文本输入框（含 focus 强调态）
LINE_EDIT = qss('''
  QLineEdit{
    color:$TEXT;
    background-color:$PANEL_BG;
    border-radius:6px;
    border:1px solid $BORDER_SOFT;
    padding:2px 8px;
  }

  QLineEdit:focus{
    border:1px solid $BORDER_FOCUS;
  }
''')

SPIN_BOX = qss('''
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
''')

# 复选框：文字暖深棕 + 暖色指示框，选中态暖橙填充
CHECK_BOX = qss('''
  QCheckBox{
    color:$TEXT;
  }

  QCheckBox::indicator{
    width:14px;
    height:14px;
    border-radius:3px;
    border:1px solid $INDICATOR_BORDER;
    background-color:$PANEL_BG;
  }

  QCheckBox::indicator:checked{
    background-color:$ACCENT;
    border:1px solid $ACCENT_DEEP;
  }
''')

TEXT_EDIT = qss('''
  QTextEdit{
    color:$TEXT;
    border-radius:6px;
    background-color:$PANEL_BG;
    border:1px solid $BORDER_SOFT;
    padding:4px;
  }

  QTextEdit:focus{
    border:1px solid $BORDER_FOCUS;
  }
''')

# 下拉框：drop-down/down-arrow 结构保留（原为 skyblue 描边），换暖棕边 + focus 态
COMBO_BOX = qss('''
  QComboBox
  {
    color:$TEXT;
    background-color:$BTN_BG;
    border-radius:6px;
    border:1px solid $BORDER;
    padding:4px 8px;
    min-height:24px;
  }

  QComboBox:hover
  {
    border:1px solid $BORDER_FOCUS;
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
''')

# 下拉弹出视图：QComboBox setView(QListView) 用（视图是独立控件，须单独 setStyleSheet）
COMBO_DROP_VIEW = qss('''
  QListView {
    background-color: $PANEL_BG;
    border: 1px solid $BORDER;
    border-radius: 0px;
    padding: 2px;
    outline: none;
    font-size: 8pt;
  }
  QListView::item {
    color: $TEXT;
    min-height: 24px;
    padding: 2px 6px;
    margin: 1px 0px;
    border-radius: 4px;
  }
  QListView::item:hover {
    background-color: $PANEL_HOVER;
  }
  QListView::item:selected {
    background-color: $PANEL_SELECT;
    color: $TEXT;
    border-radius: 4px;
  }
''')

# 列表控件：item 暖深棕字 + 暖棕下划线提示，选中态暖橙强调
LIST_WIDGET = qss('''
  QListWidget{
    border-radius:6px;
    background-color:$PANEL_BG;
    border:1px solid $BORDER_SOFT;
  }

  QListWidget::item{
    background-color:transparent;
    color:$TEXT;
    border-radius:4px;
    padding:0 2px;
  }

  QListWidget::item:hover{
    border-bottom:1px solid $BORDER_FOCUS;
  }

  QListWidget::item:selected{
    border-bottom:1px solid $BORDER_FOCUS;
    color:$ACCENT_TEXT;
  }
''')

# 滚动条：灰色 handle 换淡暖棕（结构沿用原有 6px 细条方案）
SCROLLBAR = qss('''
  QScrollBar:vertical {
    border: none;
    background: none;
    width: 6px;
    margin: 0px;
  }

  QScrollBar::handle:vertical {
    background: $SCROLLBAR;
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
    background: $SCROLLBAR;
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
''')

# 加载/退出场景共享片段：splash 启动卡与退出蒙层同源（此前逐字复制两份）
CARD_PANEL = qss('''
  QFrame {
    background-color: $PANEL_BG;
    border-radius: 10px;
    min-width: 280px;
  }
''')

TIP_LABEL = qss('font-size: 15px; color: $TEXT; border: none;')

PROGRESS_BAR = qss('''
  QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: $PROGRESS_BG;
    height: 8px;
  }
  QProgressBar::chunk {
    border-radius: 4px;
    background-color: $BORDER_FOCUS;
  }
''')

# 退出蒙层压暗层（#exitOverlay objectName 选择器）
OVERLAY = qss('''
  #exitOverlay {
    background-color: $OVERLAY_DIM;
  }
''')
