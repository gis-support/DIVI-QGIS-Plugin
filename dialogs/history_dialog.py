# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiviPluginHistoryDialog
                                 A QGIS plugin
 Integracja QGIS z platformą DIVI firmy GIS Support sp. z o. o.
                             -------------------
        begin                : 2017-01-20
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

from PyQt4 import uic
from PyQt4.QtCore import Qt, QSettings
from PyQt4.QtGui import QDialog, QColor, QItemSelectionModel
from qgis.core import QgsPoint, QGis, QgsGeometry, QgsVectorLayer, \
    QgsCoordinateReferenceSystem, QgsFeature, QgsRectangle
from qgis.gui import QgsMapCanvas, QgsRubberBand, QgsMapCanvasLayer, QgsMapToolPan
import os.path as op
import json
from osgeo.ogr import CreateGeometryFromJson
from ..models.HistoryModels import HistoryModel, HistoryProxyModel, ChangeModel
from ..utils.geometry import SetLocale_CtxDec

FORM_CLASS, _ = uic.loadUiType(op.join(
    op.dirname(__file__), 'history_dialog.ui'))

class DiviPluginHistoryDialog(QDialog, FORM_CLASS):

    def __init__(self, plugin, parent=None):
        """Constructor."""
        super(DiviPluginHistoryDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.plugin = plugin
        #self.iface = plugin.iface
        
        self.setupUi(self)
        self.initGui()
    
    def initGui(self):
        #Models
        self.tblChanges.setModel( ChangeModel() )
        proxyChanges = HistoryProxyModel()
        proxyChanges.setSourceModel( HistoryModel() )
        self.tblHistory.setModel( proxyChanges )
        #Signals
        self.plugin.tvIdentificationResult.model().sourceModel().on_history.connect( self.historyChanged )
        self.tblHistory.selectionModel().currentChanged.connect( self.currentHistoryChanged )
        #Widgets
        settings = QSettings()
        self.mapCanvas = QgsMapCanvas(self.vSplitter)
        self.mapCanvas.setDestinationCrs( QgsCoordinateReferenceSystem('EPSG:4326') )
        zoomFactor = settings.value( "/qgis/zoom_factor", 2.0, type=float )
        action = settings.value( "/qgis/wheel_action", 0, type=int)
        self.mapCanvas.setWheelAction( QgsMapCanvas.WheelAction(action), zoomFactor )
        self.mapCanvas.enableAntiAliasing( settings.value( "/qgis/enable_anti_aliasing", False, type=bool ))
        self.mapCanvas.useImageToRender( settings.value( "/qgis/use_qimage_to_render", False, type=bool ))
        self.toolPan = QgsMapToolPan( self.mapCanvas )
        self.mapCanvas.setMapTool( self.toolPan )
        #Canvas items
        self.new_geometry = QgsRubberBand(self.mapCanvas)
        self.new_geometry.setWidth(2)
        self.new_geometry.setIcon( QgsRubberBand.ICON_CIRCLE )
        g = QColor(0, 128, 0, 100)
        self.new_geometry.setColor( g )
        self.old_geometry = QgsRubberBand(self.mapCanvas)
        self.old_geometry.setWidth(2)
        self.old_geometry.setIcon( QgsRubberBand.ICON_CIRCLE )
        r = QColor(255, 0, 0, 100)
        self.old_geometry.setColor( r )
    
    def show(self, data=[]):
        model = self.tblHistory.model().sourceModel()
        model.addItems(data)
        if data:
            self.tblHistory.selectionModel().setCurrentIndex( model.index(0,0), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows )
        super(DiviPluginHistoryDialog, self).show()
    
    def historyChanged(self):
        """ Reaload data if window is visible """
        if self.isVisible():
            self.plugin.showHistoryDialog()
    
    def currentHistoryChanged(self, current, previous):
        self.new_geometry.reset()
        self.old_geometry.reset()
        self.tblChanges.model().removeRows()
        if not current.isValid():
            return
        item = current.data(Qt.UserRole)
        if item is None:
            data = {}
        else:
            data = current.data(Qt.UserRole).getDetails()
        with SetLocale_CtxDec():
            extent = None
            if data.get('new_geometry'):
                wkt = CreateGeometryFromJson( json.dumps(data['new_geometry']) ).ExportToWkt()
                geom = QgsGeometry.fromWkt( wkt )
                l = QgsVectorLayer('Point?crs=epsg:4326', 'asd', 'memory')
                self.new_geometry.setToGeometry( geom, l )
                extent = QgsRectangle(geom.boundingBox())
            if data.get('old_geometry'):
                wkt = CreateGeometryFromJson( json.dumps(data['old_geometry']) ).ExportToWkt()
                geom = QgsGeometry.fromWkt( wkt )
                l = QgsVectorLayer('Point?crs=epsg:4326', 'asd', 'memory')
                self.old_geometry.setToGeometry( geom, l )
                if extent is None:
                    extent = QgsRectangle(geom.boundingBox())
                else:
                    extent.combineExtentWith( geom.boundingBox() )
            if extent is not None:
                extent.grow(0.01)
                self.mapCanvas.setExtent( extent )
        if data.get('what_attributes', []):
            self.tblChanges.model().insertRows( 0, data.get('what_attributes', []) )
