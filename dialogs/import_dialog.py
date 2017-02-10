# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiviPluginImportDialog
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
import json
import tempfile

from PyQt4 import QtGui, uic
from PyQt4.QtCore import QSettings, Qt
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsVectorFileWriter,\
    QgsCoordinateReferenceSystem, QgsVectorLayer, QgsRasterFileWriter, QGis
from ..utils.connector import DiviConnector
from ..utils.files import readFile
from ..utils.commons import DiviJsonEncoder
from ..utils.rasters import raster2tiff
from ..widgets.ProgressMessageBar import ProgressMessageBar

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'import_dialog.ui'))


class DiviPluginImportDialog(QtGui.QDialog, FORM_CLASS):

    def __init__(self, plugin, parent=None):
        """Constructor."""
        super(DiviPluginImportDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.plugin = plugin
        self.iface = plugin.iface
        
        self.setupUi(self)
        
        self.cmbLayers.currentIndexChanged[str].connect(self.eLayerName.setText)
        
        self.loadLayers()
        self.loadProjects()
        
        self.btnOK.clicked.connect(self.uploadLayer)
        
        self.msgBar = None
        self.connector = None
    
    def loadLayers(self):
        self.cmbLayers.clear()
        for _, layer in QgsMapLayerRegistry.instance().mapLayers().iteritems():
            self.cmbLayers.addItem(layer.name(), layer)
    
    def loadProjects(self):
        self.cmbProjects.clear()
        for project in self.getModelType("Project"):
            self.cmbProjects.addItem(project.name, project)
    
    def getModelType(self, modelType, parentid=None):
        model = self.plugin.dockwidget.tvData.model().sourceModel()
        parent = model.index(0,0)
        hits = len(model.rootItem.childItems)
        indexes = model.match(
            parent,
            Qt.UserRole+2,
            modelType,
            hits,
            Qt.MatchRecursive | Qt.MatchStartsWith
        )
        for index in indexes:
            yield index.data(role=Qt.UserRole)
    
    def updateDownloadProgress(self, value):
        self.msgBar.setProgress(value)
    
    def uploadLayer(self):
        layer = self.cmbLayers.itemData(self.cmbLayers.currentIndex())
        self.msgBar = ProgressMessageBar(self.iface, self.tr(u"Uploading layer '%s'...")%layer.name(), 5, 5)
        self.msgBar.setValue(5)
        self.msgBar.setBoundries(5, 25)
        self.connector = DiviConnector()
        self.connector.uploadingProgress.connect(self.updateDownloadProgress)
        if isinstance(layer, QgsVectorLayer):
            if layer.geometryType()==QGis.NoGeometry:
                self.uploadTable(layer)
            else:
                self.uploadVectorLayer(layer)
        else:
            self.uploadRasterLayer(layer)
        self.msgBar.setValue(95)
        self.msgBar.setValue(100)
        self.msgBar.close()
        self.msgBar = None
        self.connector = None
        self.close()
    
    def uploadTable(self, table):
        """ Upload non-spatial tables """
        project = self.cmbProjects.itemData(self.cmbProjects.currentIndex())
        fields = [ field.name() for field in table.fields() ]
        data = [ feature.attributes() for feature in table.getFeatures() ]
        token = QSettings().value('divi/token', None)
        content = self.connector.sendPostRequest('/tables_tabular', 
            {'header':fields, 'data':data, 'project':project.id, 'name':self.eLayerName.text()},
            params={'token':token})
        result = json.loads(content)
        #Refresh list
        self.plugin.dockwidget.tvData.model().sourceModel().addProjectItems(
            project,
            tables = [ self.connector.diviGetTable(result['inserted']) ]
        )
    
    def uploadVectorLayer(self, layer):
        """ Upload vector layers """
        out_file = os.path.join(tempfile.gettempdir(), '%s.sqlite' % layer.name() )
        QgsVectorFileWriter.writeAsVectorFormat(layer, out_file,
            'UTF-8', QgsCoordinateReferenceSystem(4326), 'SpatiaLite')
        data = readFile( out_file, True )
        self.msgBar.setBoundries(30, 30)
        self.msgBar.setValue(30)
        project = self.cmbProjects.itemData(self.cmbProjects.currentIndex())
        data_format = '{"driver":"SQLite","name":"SpatiaLite","layer_options":["srs"],"allowed_ext":".sqlite,.db"}'
        #Send files to server
        data = self.connector.sendGeoJSON(data, self.eLayerName.text(),
            project.id, data_format
        )
        token = QSettings().value('divi/token', None)
        #Add data to DIVI
        self.msgBar.setBoundries(60, 35)
        self.msgBar.setValue(60)
        content = self.connector.sendPutRequest('/upload_gis/%s/new' % project.id,
            {
                'filename':data['filename'],
                'format':data_format,
                'session_id':data['session_id'],
                'layers':[{
                    'display_name':self.eLayerName.text(),
                    'name':data['layers'][0]['name'],
                    'srs':4326,
                    'fields':data['layers'][0]['fields']
                }]
            },
            params={'token':token})
        result = json.loads(content)
        #Refresh list
        self.plugin.dockwidget.tvData.model().sourceModel().addProjectItems(
            project,
            layers = [ self.connector.diviGetLayer(layerid) for layerid in result['uploaded'] ]
        )
    
    def uploadRasterLayer(self, layer):
        """ Upload raster layers """
        if 'geotiff' in layer.metadata().lower() and os.path.exists(layer.source()):
            #If source file is GeoTIFF than we can send it directly
            data = readFile( layer.source() )
        else:
            #Copy raster to GeoTIFF
            data = raster2tiff( layer )
        self.msgBar.setBoundries(60, 35)
        self.msgBar.setValue(60)
        project = self.cmbProjects.itemData(self.cmbProjects.currentIndex())
        content = self.connector.sendRaster(data, self.eLayerName.text(), project.id, layer.crs().postgisSrid() )
        result = content
        #Refresh list
        self.plugin.dockwidget.tvData.model().sourceModel().addProjectItems(
            project,
            [ self.connector.diviGetLayer( result['inserted'] ) ]
        )
