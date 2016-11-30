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
from PyQt4.QtGui import QCursor, QPixmap, QColor
from qgis.core import QgsFeature, QgsRasterLayer, QgsCoordinateTransform, \
    QgsCoordinateReferenceSystem
from qgis.core import QGis
from qgis.gui import QgsMapToolIdentify, QgsRubberBand

class DiviIdentifyTool(QgsMapToolIdentify):
    
    on_feature = pyqtSignal(int)
    on_activities = pyqtSignal(dict)
    on_raster = pyqtSignal(list)
    
    wgs84 = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId)
    
    cursor = QCursor(QPixmap(["16 16 3 1",
          "# c None",
          "a c #000000",
          ". c #ffffff",
          ".###########..##",
          "...########.aa.#",
          ".aa..######.aa.#",
          "#.aaa..#####..##",
          "#.aaaaa..##.aa.#",
          "##.aaaaaa...aa.#",
          "##.aaaaaa...aa.#",
          "##.aaaaa.##.aa.#",
          "###.aaaaa.#.aa.#",
          "###.aa.aaa..aa.#",
          "####..#..aa.aa.#",
          "####.####.aa.a.#",
          "##########.aa..#",
          "###########.aa..",
          "############.a.#",
          "#############.##"]), 0, 0)
        
    
    def __init__(self, parent):
        self.parent = parent
        self.iface = parent.iface
        self.canvas = parent.iface.mapCanvas()
        self.geometry = QgsRubberBand(self.canvas, QGis.Point)
        self.geometry.setColor(QColor('red'))
        self.geometry.setIconSize(7)
        self.geometry.setWidth(3)
        super(DiviIdentifyTool, self).__init__(self.canvas)
    
    def canvasReleaseEvent(self, event ):
        self.geometry.reset(QGis.Point)
        layer = self.iface.activeLayer()
        if isinstance(layer, QgsRasterLayer):
            if layer.customProperty('DiviId') is None:
                #Selected layer is not from DIVI
                self.on_raster.emit( [] )
                return
            point = self.iface.mapCanvas().getCoordinateTransform().toMapCoordinates( event.x(), event.y() )
            self.identifyRaster( point, layer.customProperty('DiviId') )
            self.geometry.addPoint( point )
            return
        if layer.customProperty('DiviId') is None:
            #Selected layer is not from DIVI
            self.on_activities.emit( {
                'attachments':[],
                'comments':[],
                'changes':[]} )
            return
        result = self.identify(event.x(), event.y(), [layer], QgsMapToolIdentify.ActiveLayer)
        if not result:
            #Clear activities panel and return if no feaure was found
            self.on_activities.emit( {
                'attachments':[],
                'comments':[],
                'changes':[]} )
            return
        feature = result[0].mFeature
        self.geometry.setToGeometry(feature.geometry(), layer)
        self.identifyVector( feature )
    
    def activate(self):
        super(DiviIdentifyTool, self).activate()
        self.connector = self.parent.dockwidget.getConnector()
        self.canvas.setCursor(self.cursor)
    
    def deactivate(self):
        super(DiviIdentifyTool, self).deactivate()
        self.geometry.reset()
        self.action().setChecked(False)
        del self.connector
    
    def identifyVector(self, feature):
        if not self.parent.identification_dock.isVisible():
            self.parent.identification_dock.show()
        fid = self.parent.ids_map[self.parent.iface.activeLayer().id()][feature.id()]
        attachments = self.connector.getAttachments( fid )
        comments = self.connector.getComments( fid )
        changes = self.connector.getChanges( fid )
        self.on_feature.emit( fid )
        self.on_activities.emit( {
            'attachments':attachments.get('data', []),
            'comments':comments.get('data', []),
            'changes':changes.get('data', [])} )
    
    def identifyRaster(self, point, layerid):
        transform = QgsCoordinateTransform(self.canvas.mapSettings().destinationCrs(), self.wgs84)
        point = transform.transform(point)
        self.on_raster.emit( self.connector.getRasterIdentification( layerid, point )['data'][0] )
    
    def toggleMapTool(self, state):
        if state:
            self.canvas.setMapTool(self)
        else:
            self.canvas.unsetMapTool(self)
