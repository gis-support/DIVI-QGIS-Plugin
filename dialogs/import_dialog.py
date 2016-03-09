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
    QgsCoordinateReferenceSystem
from ..utils.connector import DiviConnector
from ..utils.model import LayerItem
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
        else:
            parent = self.plugin.dockwidget.tvData.model().sourceModel().findItem(parentid, 'account', True)
        indexes = model.match(
            parent,
            Qt.UserRole+2,
            modelType,
            -1,
            Qt.MatchRecursive | Qt.MatchStartsWith
        )
        for index in indexes:
            yield index.data(role=Qt.UserRole)
    
    def uploadLayer(self, checked):
        def updateDownloadProgress(value):
            msgBar.setProgress(value)
        layer = self.cmbLayers.itemData(self.cmbLayers.currentIndex())
        project = self.cmbProjects.itemData(self.cmbProjects.currentIndex())
        data_format = '{"driver":"SQLite","name":"SpatiaLite","layer_options":["srs"],"allowed_ext":".sqlite,.db"}'
        msgBar = ProgressMessageBar(self.iface, self.trUtf8(u"Wysyłanie warstwy '%s'...")%layer.name(), 5, 5)
        msgBar.setValue(5)
        msgBar.setBoundries(5, 25)
        file_name = '%s.sqlite' % layer.name()
        out_file = os.path.join(tempfile.gettempdir(), file_name)
        QgsVectorFileWriter.writeAsVectorFormat(layer, out_file,
            'UTF-8', QgsCoordinateReferenceSystem(4326), 'SpatiaLite')
        data_file = QFile(out_file)
        data_file.open(QIODevice.ReadOnly)
        data = data_file.readAll()
        data_file.close()
        os.remove(out_file)
        connector = DiviConnector()
        connector.uploadingProgress.connect(updateDownloadProgress)
        msgBar.setBoundries(30, 30)
        msgBar.setValue(30)
        #Send files to server
        data = connector.sendGeoJSON(data, self.eLayerName.text(),
            project.id, data_format
        )
        token = QSettings().value('divi/token', None)
        #Add data to DIVI
        msgBar.setBoundries(60, 35)
        msgBar.setValue(60)
        content = connector.sendPutRequest('/upload_gis/%s/new' % project.id,
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
        msgBar.setValue(95)
        #Refresh list
        self.plugin.dockwidget.tvData.model().sourceModel().addProjectLayers(
            project,
            [ connector.diviGetLayer(layerid) for layerid in result['uploaded'] ]
        )
        msgBar.setValue(100)
        msgBar.close()
        msgBar = None
        self.close()
