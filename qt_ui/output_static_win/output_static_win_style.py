# -*- coding: utf-8 -*-
from qt_ui.common_style import (
  DIALOG_BASE,
  LINE_EDIT,
  LIST_WIDGET,
  SCROLLBAR,
  button_group,
)

window = (
  DIALOG_BASE + LINE_EDIT + LIST_WIDGET + SCROLLBAR
  + button_group('#browsePushButton', '#clearPushButton', '#addPushButton', '#deletePushButton', '#outputPushButton')
)
