# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'mian_window.ui'
#
# Created by: PyQt5 UI code generator 5.15.9
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(575, 294)
        MainWindow.setWindowTitle("")
        self.horizontalLayoutWidget = QtWidgets.QWidget(MainWindow)
        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(30, 170, 511, 61))
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.cacheCheckBox = QtWidgets.QCheckBox(self.horizontalLayoutWidget)
        self.cacheCheckBox.setMinimumSize(QtCore.QSize(0, 40))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.cacheCheckBox.setFont(font)
        self.cacheCheckBox.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.cacheCheckBox.setObjectName("cacheCheckBox")
        self.horizontalLayout.addWidget(self.cacheCheckBox)
        self.serverButton = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.serverButton.sizePolicy().hasHeightForWidth())
        self.serverButton.setSizePolicy(sizePolicy)
        self.serverButton.setMinimumSize(QtCore.QSize(0, 40))
        self.serverButton.setBaseSize(QtCore.QSize(0, 0))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.serverButton.setFont(font)
        self.serverButton.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.serverButton.setStyleSheet("")
        self.serverButton.setObjectName("serverButton")
        self.horizontalLayout.addWidget(self.serverButton)
        self.horizontalLayoutWidget_2 = QtWidgets.QWidget(MainWindow)
        self.horizontalLayoutWidget_2.setGeometry(QtCore.QRect(30, 50, 511, 80))
        self.horizontalLayoutWidget_2.setObjectName("horizontalLayoutWidget_2")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget_2)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.compressCheckBox = QtWidgets.QCheckBox(self.horizontalLayoutWidget_2)
        self.compressCheckBox.setMinimumSize(QtCore.QSize(0, 40))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.compressCheckBox.setFont(font)
        self.compressCheckBox.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.compressCheckBox.setObjectName("compressCheckBox")
        self.horizontalLayout_2.addWidget(self.compressCheckBox)
        self.staticDownloadButton = QtWidgets.QPushButton(self.horizontalLayoutWidget_2)
        self.staticDownloadButton.setMinimumSize(QtCore.QSize(0, 40))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.staticDownloadButton.setFont(font)
        self.staticDownloadButton.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.staticDownloadButton.setObjectName("staticDownloadButton")
        self.horizontalLayout_2.addWidget(self.staticDownloadButton)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        self.cacheCheckBox.setText(_translate("MainWindow", "缓存模式启动"))
        self.serverButton.setText(_translate("MainWindow", "启动服务"))
        self.compressCheckBox.setText(_translate("MainWindow", "下载静态资源\n"
"自动压缩图片"))
        self.staticDownloadButton.setText(_translate("MainWindow", "静态资源下载"))
