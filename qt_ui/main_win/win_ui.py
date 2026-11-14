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
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton,
    QSizePolicy, QSpacerItem, QSpinBox, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(619, 476)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.rootLayout = QVBoxLayout(self.centralwidget)
        self.rootLayout.setSpacing(10)
        self.rootLayout.setObjectName(u"rootLayout")
        self.rootLayout.setContentsMargins(20, 14, 20, 16)
        self.workDirLayout = QHBoxLayout()
        self.workDirLayout.setObjectName(u"workDirLayout")
        self.label_2 = QLabel(self.centralwidget)
        self.label_2.setObjectName(u"label_2")
        font = QFont()
        font.setPointSize(10)
        self.label_2.setFont(font)

        self.workDirLayout.addWidget(self.label_2)

        self.serverWorkDirLineEdit = QLineEdit(self.centralwidget)
        self.serverWorkDirLineEdit.setObjectName(u"serverWorkDirLineEdit")
        self.serverWorkDirLineEdit.setEnabled(False)
        self.serverWorkDirLineEdit.setMinimumSize(QSize(0, 32))
        self.serverWorkDirLineEdit.setFont(font)

        self.workDirLayout.addWidget(self.serverWorkDirLineEdit)


        self.rootLayout.addLayout(self.workDirLayout)

        self.cardServer = QFrame(self.centralwidget)
        self.cardServer.setObjectName(u"cardServer")
        self.cardServerLayout = QVBoxLayout(self.cardServer)
        self.cardServerLayout.setSpacing(8)
        self.cardServerLayout.setObjectName(u"cardServerLayout")
        self.cardServerLayout.setContentsMargins(14, 10, 14, 12)
        self.label_4 = QLabel(self.cardServer)
        self.label_4.setObjectName(u"label_4")
        font1 = QFont()
        font1.setPointSize(11)
        self.label_4.setFont(font1)

        self.cardServerLayout.addWidget(self.label_4)

        self.serverRow1 = QHBoxLayout()
        self.serverRow1.setObjectName(u"serverRow1")
        self.label = QLabel(self.cardServer)
        self.label.setObjectName(u"label")
        self.label.setFont(font)

        self.serverRow1.addWidget(self.label)

        self.serverPortSpinBox = QSpinBox(self.cardServer)
        self.serverPortSpinBox.setObjectName(u"serverPortSpinBox")
        self.serverPortSpinBox.setMinimumSize(QSize(80, 32))
        self.serverPortSpinBox.setMaximumSize(QSize(80, 32))
        self.serverPortSpinBox.setFont(font)
        self.serverPortSpinBox.setMinimum(1000)
        self.serverPortSpinBox.setMaximum(9999)
        self.serverPortSpinBox.setValue(5000)

        self.serverRow1.addWidget(self.serverPortSpinBox)

        self.label_7 = QLabel(self.cardServer)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setFont(font)

        self.serverRow1.addWidget(self.label_7)

        self.responseDelaySpinBox = QSpinBox(self.cardServer)
        self.responseDelaySpinBox.setObjectName(u"responseDelaySpinBox")
        self.responseDelaySpinBox.setMinimumSize(QSize(80, 32))
        self.responseDelaySpinBox.setMaximumSize(QSize(80, 32))
        self.responseDelaySpinBox.setFont(font)
        self.responseDelaySpinBox.setMaximum(120000)

        self.serverRow1.addWidget(self.responseDelaySpinBox)

        self.serverRow1Spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.serverRow1.addItem(self.serverRow1Spacer)

        self.serverButton = QPushButton(self.cardServer)
        self.serverButton.setObjectName(u"serverButton")
        self.serverButton.setMinimumSize(QSize(0, 32))
        self.serverButton.setFont(font)
        self.serverButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.serverRow1.addWidget(self.serverButton)


        self.cardServerLayout.addLayout(self.serverRow1)

        self.serverRow2 = QHBoxLayout()
        self.serverRow2.setObjectName(u"serverRow2")
        self.label_8 = QLabel(self.cardServer)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setFont(font)

        self.serverRow2.addWidget(self.label_8)

        self.staticLoadSpeedSpinBox = QSpinBox(self.cardServer)
        self.staticLoadSpeedSpinBox.setObjectName(u"staticLoadSpeedSpinBox")
        self.staticLoadSpeedSpinBox.setMinimumSize(QSize(80, 32))
        self.staticLoadSpeedSpinBox.setMaximumSize(QSize(80, 32))
        self.staticLoadSpeedSpinBox.setFont(font)
        self.staticLoadSpeedSpinBox.setMaximum(120000)

        self.serverRow2.addWidget(self.staticLoadSpeedSpinBox)

        self.serverRow2Spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.serverRow2.addItem(self.serverRow2Spacer)

        self.staticDownloadButton = QPushButton(self.cardServer)
        self.staticDownloadButton.setObjectName(u"staticDownloadButton")
        self.staticDownloadButton.setMinimumSize(QSize(0, 32))
        self.staticDownloadButton.setFont(font)
        self.staticDownloadButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.serverRow2.addWidget(self.staticDownloadButton)


        self.cardServerLayout.addLayout(self.serverRow2)

        self.compressCheckBox = QCheckBox(self.cardServer)
        self.compressCheckBox.setObjectName(u"compressCheckBox")
        self.compressCheckBox.setMinimumSize(QSize(0, 32))
        self.compressCheckBox.setFont(font)
        self.compressCheckBox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.compressCheckBox.setIconSize(QSize(10, 10))

        self.cardServerLayout.addWidget(self.compressCheckBox)


        self.rootLayout.addWidget(self.cardServer)

        self.cardCatch = QFrame(self.centralwidget)
        self.cardCatch.setObjectName(u"cardCatch")
        self.cardCatchLayout = QVBoxLayout(self.cardCatch)
        self.cardCatchLayout.setSpacing(8)
        self.cardCatchLayout.setObjectName(u"cardCatchLayout")
        self.cardCatchLayout.setContentsMargins(14, 10, 14, 12)
        self.label_5 = QLabel(self.cardCatch)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setFont(font1)

        self.cardCatchLayout.addWidget(self.label_5)

        self.catchRow = QHBoxLayout()
        self.catchRow.setObjectName(u"catchRow")
        self.label_3 = QLabel(self.cardCatch)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setFont(font)

        self.catchRow.addWidget(self.label_3)

        self.catchServerPortSpinBox = QSpinBox(self.cardCatch)
        self.catchServerPortSpinBox.setObjectName(u"catchServerPortSpinBox")
        self.catchServerPortSpinBox.setMinimumSize(QSize(80, 32))
        self.catchServerPortSpinBox.setMaximumSize(QSize(80, 32))
        self.catchServerPortSpinBox.setFont(font)
        self.catchServerPortSpinBox.setMinimum(1000)
        self.catchServerPortSpinBox.setMaximum(9999)
        self.catchServerPortSpinBox.setValue(8080)

        self.catchRow.addWidget(self.catchServerPortSpinBox)

        self.catchRowSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.catchRow.addItem(self.catchRowSpacer)

        self.catchServerButton = QPushButton(self.cardCatch)
        self.catchServerButton.setObjectName(u"catchServerButton")
        self.catchServerButton.setMinimumSize(QSize(0, 32))
        self.catchServerButton.setFont(font)
        self.catchServerButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.catchRow.addWidget(self.catchServerButton)


        self.cardCatchLayout.addLayout(self.catchRow)


        self.rootLayout.addWidget(self.cardCatch)

        self.cardMcp = QFrame(self.centralwidget)
        self.cardMcp.setObjectName(u"cardMcp")
        self.cardMcpLayout = QVBoxLayout(self.cardMcp)
        self.cardMcpLayout.setSpacing(8)
        self.cardMcpLayout.setObjectName(u"cardMcpLayout")
        self.cardMcpLayout.setContentsMargins(14, 10, 14, 12)
        self.label_mcp = QLabel(self.cardMcp)
        self.label_mcp.setObjectName(u"label_mcp")
        self.label_mcp.setFont(font1)

        self.cardMcpLayout.addWidget(self.label_mcp)

        self.mcpRow = QHBoxLayout()
        self.mcpRow.setObjectName(u"mcpRow")
        self.label_mcp_port = QLabel(self.cardMcp)
        self.label_mcp_port.setObjectName(u"label_mcp_port")
        self.label_mcp_port.setFont(font)

        self.mcpRow.addWidget(self.label_mcp_port)

        self.mcpServerPortSpinBox = QSpinBox(self.cardMcp)
        self.mcpServerPortSpinBox.setObjectName(u"mcpServerPortSpinBox")
        self.mcpServerPortSpinBox.setMinimumSize(QSize(80, 32))
        self.mcpServerPortSpinBox.setMaximumSize(QSize(80, 32))
        self.mcpServerPortSpinBox.setFont(font)
        self.mcpServerPortSpinBox.setMinimum(1000)
        self.mcpServerPortSpinBox.setMaximum(9999)
        self.mcpServerPortSpinBox.setValue(8765)

        self.mcpRow.addWidget(self.mcpServerPortSpinBox)

        self.mcpRowSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.mcpRow.addItem(self.mcpRowSpacer)

        self.mcpServerButton = QPushButton(self.cardMcp)
        self.mcpServerButton.setObjectName(u"mcpServerButton")
        self.mcpServerButton.setMinimumSize(QSize(0, 32))
        self.mcpServerButton.setFont(font)
        self.mcpServerButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.mcpRow.addWidget(self.mcpServerButton)


        self.cardMcpLayout.addLayout(self.mcpRow)


        self.rootLayout.addWidget(self.cardMcp)

        self.bottomSpacer = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.rootLayout.addItem(self.bottomSpacer)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle("")
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"\u5de5\u4f5c\u76ee\u5f55\uff1a", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"\u670d\u52a1\u914d\u7f6e", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u7aef\u53e3\u53f7\uff1a", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"\u54cd\u5e94\u5ef6\u65f6(ms)\uff1a", None))
        self.serverButton.setText(QCoreApplication.translate("MainWindow", u"\u542f\u52a8\u670d\u52a1", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"\u9759\u6001\u8d44\u6e90\u52a0\u8f7d\u901f\u7387(kb/s)\uff1a", None))
        self.staticDownloadButton.setText(QCoreApplication.translate("MainWindow", u"\u9759\u6001\u8d44\u6e90\u4e0b\u8f7d", None))
        self.compressCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u4e0b\u8f7d\u9759\u6001\u8d44\u6e90\u81ea\u52a8\u538b\u7f29\u56fe\u7247", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"\u6293\u5305\u914d\u7f6e", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"\u7aef\u53e3\u53f7\uff1a", None))
        self.catchServerButton.setText(QCoreApplication.translate("MainWindow", u"\u542f\u52a8\u6293\u5305\u670d\u52a1", None))
        self.label_mcp.setText(QCoreApplication.translate("MainWindow", u"MCP \u914d\u7f6e", None))
        self.label_mcp_port.setText(QCoreApplication.translate("MainWindow", u"\u7aef\u53e3\u53f7\uff1a", None))
        self.mcpServerButton.setText(QCoreApplication.translate("MainWindow", u"\u542f\u52a8MCP\u670d\u52a1", None))
    # retranslateUi

