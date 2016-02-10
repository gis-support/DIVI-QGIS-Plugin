# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiviPluginDockWidget
                                 A QGIS plugin
 Integracja QGIS z platformą DIVI firmy GIS Support sp. z o. o.
                             -------------------
        begin                : 2016-02-09
        git sha              : $Format:%H$
        copyright            : (C) 2016 by GIS Support sp. z o. o.
        email                : info@gis-support.pl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt4 import QtGui, uic
from PyQt4.QtCore import pyqtSignal, QSettings
from qgis.core import QgsMessageLog
from ..utils.connector import DiviConnector
from ..utils.model import AccountItem, DiviModel

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dockwidget.ui'))


class DiviPluginDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(DiviPluginDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.iface = iface
        self.token = QSettings().value('divi/token', None)
        self.setupUi(self)
        self.tvData.setModel( DiviModel() )
        self.connector = DiviConnector()
        #Signals
        self.btnConnect.clicked.connect(self.diviConnect)
        self.connector.tokenSetted.connect(self.setToken)
    
    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
    
    def diviConnect(self, checked):
        self.tvData.model().addData( *self.connector.diviFeatchData() )
    
    def setToken(self, token):
        self.token = token
