# -*- coding: utf-8 -*-
from qt_ui.common_style import LIST_WIDGET, MODULE_TEXT, SCROLLBAR, button_group

window = (
  MODULE_TEXT + LIST_WIDGET + SCROLLBAR
  + button_group('#clearPushButton', '#addPushButton', '#editPushButton', '#deletePushButton')
)
