# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'win_ui.ui'
##
## Created by: Qt User Interface Compiler version 6.10.3
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QLabel,
    QLayout, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(520, 320)
        self.verticalLayoutWidget = QWidget(Dialog)
        self.verticalLayoutWidget.setObjectName(u"verticalLayoutWidget")
        self.verticalLayoutWidget.setGeometry(QRect(20, 20, 481, 181))
        self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setSizeConstraint(QLayout.SetMaximumSize)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.confirmPushButton = QPushButton(Dialog)
        self.confirmPushButton.setObjectName(u"confirmPushButton")
        self.confirmPushButton.setGeometry(QRect(430, 270, 71, 30))
        font = QFont()
        font.setPointSize(10)
        self.confirmPushButton.setFont(font)
        self.confirmPushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(20, 220, 101, 30))
        self.label.setMinimumSize(QSize(0, 30))
        self.label.setFont(font)
        self.timeoutSpinBox = QSpinBox(Dialog)
        self.timeoutSpinBox.setObjectName(u"timeoutSpinBox")
        self.timeoutSpinBox.setGeometry(QRect(120, 220, 71, 30))
        self.timeoutSpinBox.setMinimumSize(QSize(0, 30))
        self.timeoutSpinBox.setFont(font)
        self.timeoutSpinBox.setMinimum(5)
        self.timeoutSpinBox.setMaximum(300)
        self.autoAdjustTimeoutCheckBox = QCheckBox(Dialog)
        self.autoAdjustTimeoutCheckBox.setObjectName(u"autoAdjustTimeoutCheckBox")
        self.autoAdjustTimeoutCheckBox.setGeometry(QRect(260, 220, 211, 30))
        self.autoAdjustTimeoutCheckBox.setMinimumSize(QSize(0, 30))
        self.autoAdjustTimeoutCheckBox.setFont(font)
        self.autoAdjustTimeoutCheckBox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.confirmPushButton.setText(QCoreApplication.translate("Dialog", u"\u786e\u5b9a", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"\u4e0b\u8f7d\u8d85\u65f6\u65f6\u95f4(s)", None))
        self.autoAdjustTimeoutCheckBox.setText(QCoreApplication.translate("Dialog", u"\u52a8\u6001\u8c03\u6574\u4e0b\u8f7d\u8fde\u63a5\u8d85\u65f6\u65f6\u95f4", None))
    # retranslateUi

