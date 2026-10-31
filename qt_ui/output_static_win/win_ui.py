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
from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
    QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(580, 289)
        font = QFont()
        font.setPointSize(9)
        Dialog.setFont(font)
        self.addPushButton = QPushButton(Dialog)
        self.addPushButton.setObjectName(u"addPushButton")
        self.addPushButton.setGeometry(QRect(470, 110, 91, 30))
        self.addPushButton.setMinimumSize(QSize(0, 30))
        font1 = QFont()
        font1.setPointSize(10)
        self.addPushButton.setFont(font1)
        self.addPushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.deletePushButton = QPushButton(Dialog)
        self.deletePushButton.setObjectName(u"deletePushButton")
        self.deletePushButton.setGeometry(QRect(470, 150, 91, 30))
        self.deletePushButton.setMinimumSize(QSize(0, 30))
        self.deletePushButton.setFont(font1)
        self.deletePushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.outputPushButton = QPushButton(Dialog)
        self.outputPushButton.setObjectName(u"outputPushButton")
        self.outputPushButton.setGeometry(QRect(470, 190, 91, 30))
        self.outputPushButton.setMinimumSize(QSize(0, 30))
        self.outputPushButton.setFont(font1)
        self.outputPushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.downloadLogListWidget = QListWidget(Dialog)
        self.downloadLogListWidget.setObjectName(u"downloadLogListWidget")
        self.downloadLogListWidget.setGeometry(QRect(20, 70, 431, 201))
        self.downloadLogListWidget.setFont(font1)
        self.clearPushButton = QPushButton(Dialog)
        self.clearPushButton.setObjectName(u"clearPushButton")
        self.clearPushButton.setGeometry(QRect(470, 70, 91, 31))
        self.clearPushButton.setMinimumSize(QSize(0, 30))
        self.clearPushButton.setFont(font1)
        self.clearPushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.browsePushButton = QPushButton(Dialog)
        self.browsePushButton.setObjectName(u"browsePushButton")
        self.browsePushButton.setGeometry(QRect(470, 20, 89, 30))
        self.browsePushButton.setMinimumSize(QSize(0, 30))
        self.browsePushButton.setFont(font1)
        self.browsePushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.browseLineEdit = QLineEdit(Dialog)
        self.browseLineEdit.setObjectName(u"browseLineEdit")
        self.browseLineEdit.setEnabled(False)
        self.browseLineEdit.setGeometry(QRect(78, 20, 371, 30))
        self.browseLineEdit.setMinimumSize(QSize(0, 30))
        self.browseLineEdit.setFont(font1)
        self.browseLineEdit.setReadOnly(False)
        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(20, 25, 61, 21))
        self.label.setFont(font1)

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.addPushButton.setText(QCoreApplication.translate("Dialog", u"\u6dfb\u52a0", None))
        self.deletePushButton.setText(QCoreApplication.translate("Dialog", u"\u5220\u9664", None))
        self.outputPushButton.setText(QCoreApplication.translate("Dialog", u"\u5bfc\u51fa", None))
        self.clearPushButton.setText(QCoreApplication.translate("Dialog", u"\u6e05\u7a7a", None))
        self.browsePushButton.setText(QCoreApplication.translate("Dialog", u"\u6d4f\u89c8", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"\u5bfc\u51fa\u5230\uff1a", None))
    # retranslateUi

