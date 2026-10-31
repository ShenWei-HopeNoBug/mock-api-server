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
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpinBox,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(619, 460)
        self.horizontalLayoutWidget = QWidget(MainWindow)
        self.horizontalLayoutWidget.setObjectName(u"horizontalLayoutWidget")
        self.horizontalLayoutWidget.setGeometry(QRect(440, 340, 161, 41))
        self.horizontalLayout = QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.serverButton = QPushButton(self.horizontalLayoutWidget)
        self.serverButton.setObjectName(u"serverButton")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.serverButton.sizePolicy().hasHeightForWidth())
        self.serverButton.setSizePolicy(sizePolicy)
        self.serverButton.setMinimumSize(QSize(0, 32))
        self.serverButton.setBaseSize(QSize(0, 0))
        font = QFont()
        font.setPointSize(10)
        self.serverButton.setFont(font)
        self.serverButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.serverButton.setStyleSheet(u"")

        self.horizontalLayout.addWidget(self.serverButton)

        self.horizontalLayoutWidget_2 = QWidget(MainWindow)
        self.horizontalLayoutWidget_2.setObjectName(u"horizontalLayoutWidget_2")
        self.horizontalLayoutWidget_2.setGeometry(QRect(440, 280, 161, 41))
        self.horizontalLayout_2 = QHBoxLayout(self.horizontalLayoutWidget_2)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.staticDownloadButton = QPushButton(self.horizontalLayoutWidget_2)
        self.staticDownloadButton.setObjectName(u"staticDownloadButton")
        self.staticDownloadButton.setMinimumSize(QSize(0, 32))
        self.staticDownloadButton.setFont(font)
        self.staticDownloadButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.horizontalLayout_2.addWidget(self.staticDownloadButton)

        self.horizontalLayoutWidget_4 = QWidget(MainWindow)
        self.horizontalLayoutWidget_4.setObjectName(u"horizontalLayoutWidget_4")
        self.horizontalLayoutWidget_4.setGeometry(QRect(30, 340, 141, 41))
        self.horizontalLayout_4 = QHBoxLayout(self.horizontalLayoutWidget_4)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self.horizontalLayoutWidget_4)
        self.label.setObjectName(u"label")
        self.label.setFont(font)

        self.horizontalLayout_4.addWidget(self.label)

        self.serverPortSpinBox = QSpinBox(self.horizontalLayoutWidget_4)
        self.serverPortSpinBox.setObjectName(u"serverPortSpinBox")
        self.serverPortSpinBox.setMinimumSize(QSize(80, 32))
        self.serverPortSpinBox.setMaximumSize(QSize(80, 32))
        self.serverPortSpinBox.setFont(font)
        self.serverPortSpinBox.setMinimum(1000)
        self.serverPortSpinBox.setMaximum(9999)
        self.serverPortSpinBox.setValue(5000)

        self.horizontalLayout_4.addWidget(self.serverPortSpinBox)

        self.horizontalLayoutWidget_5 = QWidget(MainWindow)
        self.horizontalLayoutWidget_5.setObjectName(u"horizontalLayoutWidget_5")
        self.horizontalLayoutWidget_5.setGeometry(QRect(30, 40, 571, 42))
        self.horizontalLayout_5 = QHBoxLayout(self.horizontalLayoutWidget_5)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.label_2 = QLabel(self.horizontalLayoutWidget_5)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setMinimumSize(QSize(0, 24))
        self.label_2.setFont(font)

        self.horizontalLayout_5.addWidget(self.label_2)

        self.serverWorkDirLineEdit = QLineEdit(self.horizontalLayoutWidget_5)
        self.serverWorkDirLineEdit.setObjectName(u"serverWorkDirLineEdit")
        self.serverWorkDirLineEdit.setEnabled(False)
        self.serverWorkDirLineEdit.setMinimumSize(QSize(0, 32))
        self.serverWorkDirLineEdit.setFont(font)

        self.horizontalLayout_5.addWidget(self.serverWorkDirLineEdit)

        self.horizontalLayoutWidget_3 = QWidget(MainWindow)
        self.horizontalLayoutWidget_3.setObjectName(u"horizontalLayoutWidget_3")
        self.horizontalLayoutWidget_3.setGeometry(QRect(30, 120, 141, 41))
        self.horizontalLayout_3 = QHBoxLayout(self.horizontalLayoutWidget_3)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.label_3 = QLabel(self.horizontalLayoutWidget_3)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setMinimumSize(QSize(0, 32))
        self.label_3.setFont(font)

        self.horizontalLayout_3.addWidget(self.label_3)

        self.catchServerPortSpinBox = QSpinBox(self.horizontalLayoutWidget_3)
        self.catchServerPortSpinBox.setObjectName(u"catchServerPortSpinBox")
        self.catchServerPortSpinBox.setMinimumSize(QSize(80, 32))
        self.catchServerPortSpinBox.setMaximumSize(QSize(80, 32))
        self.catchServerPortSpinBox.setBaseSize(QSize(0, 0))
        self.catchServerPortSpinBox.setFont(font)
        self.catchServerPortSpinBox.setMinimum(1000)
        self.catchServerPortSpinBox.setMaximum(9999)
        self.catchServerPortSpinBox.setValue(8080)

        self.horizontalLayout_3.addWidget(self.catchServerPortSpinBox)

        self.label_4 = QLabel(MainWindow)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setGeometry(QRect(20, 240, 161, 40))
        self.label_4.setMinimumSize(QSize(0, 40))
        font1 = QFont()
        font1.setPointSize(12)
        self.label_4.setFont(font1)
        self.label_5 = QLabel(MainWindow)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setGeometry(QRect(20, 80, 161, 40))
        self.label_5.setMinimumSize(QSize(0, 40))
        self.label_5.setFont(font1)
        self.horizontalLayoutWidget_6 = QWidget(MainWindow)
        self.horizontalLayoutWidget_6.setObjectName(u"horizontalLayoutWidget_6")
        self.horizontalLayoutWidget_6.setGeometry(QRect(440, 120, 161, 41))
        self.horizontalLayout_6 = QHBoxLayout(self.horizontalLayoutWidget_6)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.catchServerButton = QPushButton(self.horizontalLayoutWidget_6)
        self.catchServerButton.setObjectName(u"catchServerButton")
        self.catchServerButton.setMinimumSize(QSize(0, 32))
        self.catchServerButton.setFont(font)
        self.catchServerButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.horizontalLayout_6.addWidget(self.catchServerButton)

        self.label_mcp = QLabel(MainWindow)
        self.label_mcp.setObjectName(u"label_mcp")
        self.label_mcp.setGeometry(QRect(20, 160, 161, 40))
        self.label_mcp.setMinimumSize(QSize(0, 40))
        self.label_mcp.setFont(font1)
        self.horizontalLayoutWidget_mcp_port = QWidget(MainWindow)
        self.horizontalLayoutWidget_mcp_port.setObjectName(u"horizontalLayoutWidget_mcp_port")
        self.horizontalLayoutWidget_mcp_port.setGeometry(QRect(30, 200, 141, 41))
        self.horizontalLayout_mcp_port = QHBoxLayout(self.horizontalLayoutWidget_mcp_port)
        self.horizontalLayout_mcp_port.setObjectName(u"horizontalLayout_mcp_port")
        self.horizontalLayout_mcp_port.setContentsMargins(0, 0, 0, 0)
        self.label_mcp_port = QLabel(self.horizontalLayoutWidget_mcp_port)
        self.label_mcp_port.setObjectName(u"label_mcp_port")
        self.label_mcp_port.setFont(font)

        self.horizontalLayout_mcp_port.addWidget(self.label_mcp_port)

        self.mcpServerPortSpinBox = QSpinBox(self.horizontalLayoutWidget_mcp_port)
        self.mcpServerPortSpinBox.setObjectName(u"mcpServerPortSpinBox")
        self.mcpServerPortSpinBox.setMinimumSize(QSize(80, 32))
        self.mcpServerPortSpinBox.setMaximumSize(QSize(80, 32))
        self.mcpServerPortSpinBox.setFont(font)
        self.mcpServerPortSpinBox.setMinimum(1000)
        self.mcpServerPortSpinBox.setMaximum(9999)
        self.mcpServerPortSpinBox.setValue(8765)

        self.horizontalLayout_mcp_port.addWidget(self.mcpServerPortSpinBox)

        self.horizontalLayoutWidget_mcp_btn = QWidget(MainWindow)
        self.horizontalLayoutWidget_mcp_btn.setObjectName(u"horizontalLayoutWidget_mcp_btn")
        self.horizontalLayoutWidget_mcp_btn.setGeometry(QRect(440, 200, 161, 41))
        self.horizontalLayout_mcp_btn = QHBoxLayout(self.horizontalLayoutWidget_mcp_btn)
        self.horizontalLayout_mcp_btn.setObjectName(u"horizontalLayout_mcp_btn")
        self.horizontalLayout_mcp_btn.setContentsMargins(0, 0, 0, 0)
        self.mcpServerButton = QPushButton(self.horizontalLayoutWidget_mcp_btn)
        self.mcpServerButton.setObjectName(u"mcpServerButton")
        self.mcpServerButton.setMinimumSize(QSize(0, 32))
        self.mcpServerButton.setFont(font)
        self.mcpServerButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.horizontalLayout_mcp_btn.addWidget(self.mcpServerButton)

        self.horizontalLayoutWidget_7 = QWidget(MainWindow)
        self.horizontalLayoutWidget_7.setObjectName(u"horizontalLayoutWidget_7")
        self.horizontalLayoutWidget_7.setGeometry(QRect(220, 340, 181, 41))
        self.horizontalLayout_7 = QHBoxLayout(self.horizontalLayoutWidget_7)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.label_7 = QLabel(self.horizontalLayoutWidget_7)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setMinimumSize(QSize(0, 32))
        self.label_7.setFont(font)

        self.horizontalLayout_7.addWidget(self.label_7)

        self.responseDelaySpinBox = QSpinBox(self.horizontalLayoutWidget_7)
        self.responseDelaySpinBox.setObjectName(u"responseDelaySpinBox")
        self.responseDelaySpinBox.setMinimumSize(QSize(80, 32))
        self.responseDelaySpinBox.setMaximumSize(QSize(80, 32))
        self.responseDelaySpinBox.setFont(font)
        self.responseDelaySpinBox.setMaximum(120000)

        self.horizontalLayout_7.addWidget(self.responseDelaySpinBox)

        self.horizontalLayoutWidget_8 = QWidget(MainWindow)
        self.horizontalLayoutWidget_8.setObjectName(u"horizontalLayoutWidget_8")
        self.horizontalLayoutWidget_8.setGeometry(QRect(30, 390, 251, 41))
        self.horizontalLayout_8 = QHBoxLayout(self.horizontalLayoutWidget_8)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.label_8 = QLabel(self.horizontalLayoutWidget_8)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setFont(font)

        self.horizontalLayout_8.addWidget(self.label_8)

        self.staticLoadSpeedSpinBox = QSpinBox(self.horizontalLayoutWidget_8)
        self.staticLoadSpeedSpinBox.setObjectName(u"staticLoadSpeedSpinBox")
        self.staticLoadSpeedSpinBox.setMinimumSize(QSize(80, 32))
        self.staticLoadSpeedSpinBox.setMaximumSize(QSize(80, 32))
        self.staticLoadSpeedSpinBox.setFont(font)
        self.staticLoadSpeedSpinBox.setMaximum(120000)

        self.horizontalLayout_8.addWidget(self.staticLoadSpeedSpinBox)

        self.horizontalLayoutWidget_10 = QWidget(MainWindow)
        self.horizontalLayoutWidget_10.setObjectName(u"horizontalLayoutWidget_10")
        self.horizontalLayoutWidget_10.setGeometry(QRect(30, 280, 201, 41))
        self.horizontalLayout_10 = QHBoxLayout(self.horizontalLayoutWidget_10)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.horizontalLayout_10.setContentsMargins(0, 0, 0, 0)
        self.compressCheckBox = QCheckBox(self.horizontalLayoutWidget_10)
        self.compressCheckBox.setObjectName(u"compressCheckBox")
        self.compressCheckBox.setMinimumSize(QSize(0, 32))
        self.compressCheckBox.setFont(font)
        self.compressCheckBox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.compressCheckBox.setIconSize(QSize(10, 10))

        self.horizontalLayout_10.addWidget(self.compressCheckBox)


        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle("")
        self.serverButton.setText(QCoreApplication.translate("MainWindow", u"\u542f\u52a8\u670d\u52a1", None))
        self.staticDownloadButton.setText(QCoreApplication.translate("MainWindow", u"\u9759\u6001\u8d44\u6e90\u4e0b\u8f7d", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u7aef\u53e3\u53f7\uff1a", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"\u5de5\u4f5c\u76ee\u5f55\uff1a", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"\u7aef\u53e3\u53f7\uff1a", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"\u3010\u670d\u52a1\u914d\u7f6e\u3011", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"\u3010\u6293\u5305\u914d\u7f6e\u3011", None))
        self.catchServerButton.setText(QCoreApplication.translate("MainWindow", u"\u542f\u52a8\u6293\u5305\u670d\u52a1", None))
        self.label_mcp.setText(QCoreApplication.translate("MainWindow", u"\u3010MCP\u914d\u7f6e\u3011", None))
        self.label_mcp_port.setText(QCoreApplication.translate("MainWindow", u"\u7aef\u53e3\u53f7\uff1a", None))
        self.mcpServerButton.setText(QCoreApplication.translate("MainWindow", u"\u542f\u52a8MCP\u670d\u52a1", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"\u54cd\u5e94\u5ef6\u65f6(ms)\uff1a", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"\u9759\u6001\u8d44\u6e90\u52a0\u8f7d\u901f\u7387(kb/s)\uff1a", None))
        self.compressCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u4e0b\u8f7d\u9759\u6001\u8d44\u6e90\u81ea\u52a8\u538b\u7f29\u56fe\u7247", None))
    # retranslateUi

