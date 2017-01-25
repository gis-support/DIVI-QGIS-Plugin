# -*- coding: utf-8 -*-
"""
/***************************************************************************
 widgets
                                 A QGIS plugin
 Integracja QGIS z platformą DIVI firmy GIS Support sp. z o. o.
                             -------------------
        begin                : 2017-01-25
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

from PyQt4.QtCore import QObject, QPyNullVariant
from PyQt4.QtGui import QProgressBar
from qgis.core import QgsMessageLog

class ProgressMessageBar(QObject):
    
    def __init__(self, iface, message, minValue=10, delta=40):
        super(ProgressMessageBar, self).__init__()
        self.iface = iface
        self.minValue = minValue
        self.delta = delta
        self.progress = None
        self.msgBar = None
        if self.iface is not None:
            self.msgBar = self.iface.messageBar().createMessage('DIVI',message)
            self.progress = QProgressBar()
            self.msgBar.layout().addWidget(self.progress)
            self.iface.messageBar().pushWidget(self.msgBar, self.iface.messageBar().INFO)
    
    def setProgress(self, value):
        try:
            progress = self.minValue+int(self.delta*value)
            if self.iface is not None:
                self.iface.mainWindow().statusBar().showMessage( self.tr("Loading layer {} %").format(progress) )
                self.progress.setValue(progress)
        except RuntimeError:
            pass
    
    def setValue(self, value):
        try:
            if self.iface is not None:
                self.iface.mainWindow().statusBar().showMessage( self.tr("Loading layer {} %").format(value) )
                self.progress.setValue(value)
        except RuntimeError:
            pass
    
    def setBoundries(self, minValue=None, delta=None):
        if minValue is not None:
            self.minValue = minValue
        if delta is not None:
            self.delta = delta
    
    def close(self):
        if self.iface is not None:
            self.iface.messageBar().clearWidgets()
            self.progress = None
            self.msgBar = None
