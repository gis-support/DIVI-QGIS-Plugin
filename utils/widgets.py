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

from PyQt4.QtCore import QObject
from PyQt4.QtGui import QProgressBar
from qgis.core import QgsMessageLog

class ProgressMessageBar(QObject):
    
    def __init__(self, iface, message, minValue=10, delta=40):
        super(ProgressMessageBar, self).__init__()
        self.iface = iface
        self.minValue = minValue
        self.delta = delta
        if self.iface is not None:
            msgBar = self.iface.messageBar().createMessage('DIVI',message)
            self.progress = QProgressBar()
            msgBar.layout().addWidget(self.progress)
            self.iface.messageBar().pushWidget(msgBar, self.iface.messageBar().INFO)
        else:
            self.progress = None
    
    def setProgress(self, value):
        self.progress.setValue(self.minValue+int(self.delta*value))
    
    def setBoundries(self, minValue=None, delta=None):
        if minValue is not None:
            self.minValue = minValue
        if delta is not None:
            self.delta = delta
    
    def close(self):
        if self.iface is not None:
            self.iface.messageBar().clearWidgets()
