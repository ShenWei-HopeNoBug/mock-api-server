# -*- coding: utf-8 -*-
from qt_ui.common_style import COMBO_BOX, DIALOG_BASE, button_group

# 下拉列表视图样式由 server_config_dialog 中 QListView.setStyleSheet 单独控制
window = DIALOG_BASE + COMBO_BOX + button_group('#confirmPushButton')
