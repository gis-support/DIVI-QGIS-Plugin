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
from PyQt4.QtCore import QSettings, Qt, QFile, QIODevice
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsVectorFileWriter,\
    QgsCoordinateReferenceSystem, QgsVectorLayer, QgsRasterFileWriter, QGis
from ..utils.connector import DiviConnector
from ..utils.widgets import ProgressMessageBar, DiviJsonEncoder

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
        self.loadAccounts()
        self.loadProjects(self.cmbAccounts.currentIndex())
        
        self.cmbAccounts.currentIndexChanged[int].connect(self.loadProjects)
        self.btnOK.clicked.connect(self.uploadLayer)
        
        self.msgBar = None
        self.connector = None
    
    def loadLayers(self):
        self.cmbLayers.clear()
        for _, layer in QgsMapLayerRegistry.instance().mapLayers().iteritems():
            self.cmbLayers.addItem(layer.name(), layer)
    
    def loadAccounts(self):
        self.cmbAccounts.clear()
        for account in self.getModelType("Account"):
            self.cmbAccounts.addItem(account.name, account.id)
    
    def loadProjects(self, account):
        accountid = self.cmbAccounts.itemData(account)
        self.cmbProjects.clear()
        for project in self.getModelType("Project", accountid):
            self.cmbProjects.addItem(project.name, project)
    
    def getModelType(self, modelType, parentid=None):
        model = self.plugin.dockwidget.tvData.model().sourceModel()
        if parentid is None:
            parent = model.index(0,0)
            #Accounts count
            hits = len(model.rootItem.childItems)
        else:
            parent = model.findItem(parentid, 'account', True)
            hits = len(parent.data(role=Qt.UserRole).childItems)
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
        account = self.cmbAccounts.itemData(self.cmbAccounts.currentIndex())
        fields = [ field.name() for field in table.fields() ]
        data = [ feature.attributes() for feature in table.getFeatures() ]
        token = QSettings().value('divi/token', None)
        content = self.connector.sendPostRequest('/tables_tabular', 
            {'header':fields, 'data':data, 'project':project.id, 'name':self.eLayerName.text()},
            params={'token':token, 'account':account})
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
        data = self.readFile( out_file, True )
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
            data = self.readFile( layer.source() )
        else:
            #Copy raster to GeoTIFF
            #Show raster copy progress
            progress = QtGui.QProgressDialog()
            out_file = os.path.join(tempfile.gettempdir(), '%s.tiff' % layer.name())
            writer = QgsRasterFileWriter( out_file )
            writer.setCreateOptions(['COMPRESS=DEFLATE'])
            writer.writeRaster( layer.pipe(), layer.width(), layer.height(), layer.dataProvider().extent(), layer.crs(), progress )
            del writer
            del progress
            data = self.readFile( out_file, True )
        self.msgBar.setBoundries(60, 35)
        self.msgBar.setValue(60)
        project = self.cmbProjects.itemData(self.cmbProjects.currentIndex())
        content = self.connector.sendRaster(data, self.eLayerName.text(), project.id, layer.crs().postgisSrid() )
        result = content
        #Refresh list
        self.plugin.dockwidget.tvData.model().sourceModel().addProjectLayers(
            project,
            [ self.connector.diviGetLayer( result['inserted'] ) ]
        )
    
    @staticmethod
    def readFile(path, delete_after=False):
        data_file = QFile( path )
        data_file.open(QIODevice.ReadOnly)
        data = data_file.readAll()
        data_file.close()
        if delete_after:
            os.remove( path )
        return data
