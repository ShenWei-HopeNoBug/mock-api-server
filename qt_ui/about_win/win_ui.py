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
from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QSizePolicy,
    QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(479, 100)
        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(20, 20, 50, 30))
        self.label.setMinimumSize(QSize(0, 30))
        font = QFont()
        font.setPointSize(10)
        self.label.setFont(font)
        self.versionLable = QLabel(Dialog)
        self.versionLable.setObjectName(u"versionLable")
        self.versionLable.setGeometry(QRect(80, 20, 380, 30))
        self.versionLable.setMinimumSize(QSize(0, 30))
        self.versionLable.setFont(font)
        self.label_2 = QLabel(Dialog)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(20, 50, 50, 32))
        self.label_2.setMinimumSize(QSize(0, 30))
        self.label_2.setFont(font)

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"\u7248\u672c\u53f7\uff1a", None))
        self.versionLable.setText("")
        self.label_2.setText(QCoreApplication.translate("Dialog", u"github\uff1a", None))
    # retranslateUi

