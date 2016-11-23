# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Identify tool
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

from PyQt4.QtCore import pyqtSignal
from qgis.core import QgsFeature
from qgis.gui import QgsMapToolIdentifyFeature

class DiviIdentifyTool(QgsMapToolIdentifyFeature):
    
    on_feature = pyqtSignal(int)
    on_activities = pyqtSignal(dict)
    
    def __init__(self, parent):
        self.parent = parent
        self.canvas = parent.iface.mapCanvas()
        super(DiviIdentifyTool, self).__init__(self.canvas, parent.iface.activeLayer())
        #Signals
        self.featureIdentified[QgsFeature].connect( self.identifyFeature )
    
    def activate(self):
        super(DiviIdentifyTool, self).activate()
        self.setLayer( self.parent.iface.activeLayer() )
        self.connector = self.parent.dockwidget.getConnector()
    
    def deactivate(self):
        super(DiviIdentifyTool, self).deactivate()
        self.action().setChecked(False)
        
        del self.connector
    
    def identifyFeature(self, feature):
        fid = self.parent.ids_map[self.parent.iface.activeLayer().id()][feature.id()]
        attachments = self.connector.getAttachments( str(fid) )
        comments = self.connector.getComments( str(fid) )
        self.on_feature.emit( fid )
        self.on_activities.emit( {'attachments':attachments.get('data', []), 'comments':comments.get('data', [])} )
    
    def toggleMapTool(self, state):
        if state:
            self.canvas.setMapTool(self)
        else:
            self.canvas.unsetMapTool(self)
