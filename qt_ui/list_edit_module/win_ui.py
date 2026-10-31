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
from PySide6.QtWidgets import (QApplication, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QWidget)

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(500, 200)
        self.listLabel = QLabel(Form)
        self.listLabel.setObjectName(u"listLabel")
        self.listLabel.setGeometry(QRect(10, 10, 391, 30))
        self.listLabel.setMinimumSize(QSize(0, 30))
        font = QFont()
        font.setPointSize(10)
        self.listLabel.setFont(font)
        self.editPushButton = QPushButton(Form)
        self.editPushButton.setObjectName(u"editPushButton")
        self.editPushButton.setGeometry(QRect(420, 120, 71, 30))
        self.editPushButton.setMinimumSize(QSize(0, 30))
        self.editPushButton.setFont(font)
        self.editPushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.listWidget = QListWidget(Form)
        self.listWidget.setObjectName(u"listWidget")
        self.listWidget.setGeometry(QRect(10, 40, 391, 151))
        self.listWidget.setFont(font)
        self.deletePushButton = QPushButton(Form)
        self.deletePushButton.setObjectName(u"deletePushButton")
        self.deletePushButton.setGeometry(QRect(420, 160, 71, 30))
        self.deletePushButton.setMinimumSize(QSize(0, 30))
        self.deletePushButton.setFont(font)
        self.deletePushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.addPushButton = QPushButton(Form)
        self.addPushButton.setObjectName(u"addPushButton")
        self.addPushButton.setGeometry(QRect(420, 80, 71, 30))
        self.addPushButton.setMinimumSize(QSize(0, 30))
        self.addPushButton.setFont(font)
        self.addPushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clearPushButton = QPushButton(Form)
        self.clearPushButton.setObjectName(u"clearPushButton")
        self.clearPushButton.setGeometry(QRect(420, 40, 71, 30))
        self.clearPushButton.setMinimumSize(QSize(0, 30))
        self.clearPushButton.setFont(font)
        self.clearPushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.listLabel.setText("")
        self.editPushButton.setText(QCoreApplication.translate("Form", u"\u7f16\u8f91", None))
        self.deletePushButton.setText(QCoreApplication.translate("Form", u"\u5220\u9664", None))
        self.addPushButton.setText(QCoreApplication.translate("Form", u"\u65b0\u589e", None))
        self.clearPushButton.setText(QCoreApplication.translate("Form", u"\u6e05\u7a7a", None))
    # retranslateUi

