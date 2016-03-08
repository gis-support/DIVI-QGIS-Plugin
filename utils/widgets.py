# -*- coding: utf-8 -*-
"""
/***************************************************************************
 widgets
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

from PyQt4.QtCore import QObject, QPyNullVariant, QDate, Qt
from PyQt4.QtGui import QProgressBar
from qgis.core import QgsMessageLog
import json

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
                self.iface.mainWindow().statusBar().showMessage( self.trUtf8("Ładowanie warstwy {} %").format(progress) )
                self.progress.setValue(progress)
        except RuntimeError:
            pass
    
    def setValue(self, value):
        try:
            if self.iface is not None:
                self.iface.mainWindow().statusBar().showMessage( self.trUtf8("Ładowanie warstwy {} %").format(value) )
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

class DiviJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, QPyNullVariant):
            return None
        elif isinstance(obj, QDate):
            return obj.toString(Qt.ISODate)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)
