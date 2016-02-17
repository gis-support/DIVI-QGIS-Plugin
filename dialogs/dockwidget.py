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
from PyQt4.QtCore import pyqtSignal, QSettings, Qt
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsVectorLayer
from qgis.gui import QgsMessageBar
from ..utils.connector import DiviConnector
from ..utils.data import getFields, addFeatures
from ..utils.model import DiviModel, LayerItem, TableItem
from ..utils.widgets import ProgressMessageBar

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
        self.user = QSettings().value('divi/email', None)
        self.setupUi(self)
        self.tvData.setModel( DiviModel() )
        self.setLogginStatus(bool(self.token))
        if self.token:
            self.diviConnection(True, auto_login=False)
        #Signals
        self.btnConnect.clicked.connect(self.diviConnection)
        self.tvData.doubleClicked.connect(self.dblClick)
        self.tvData.customContextMenuRequested.connect(self.showMenu)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect( self.layersRemoved )
    
    def getConnector(self, auto_login=True, progress=None, progressMin=0, progressMax=40):
        connector = DiviConnector(iface=self.iface, auto_login=auto_login,
            progress=progress, progressMin=progressMin, progressMax=progressMax)
        connector.diviLogged.connect(self.setUserData)
        return connector
    
    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
    
    def diviConnection(self, checked, auto_login=True):
        if checked:
            #Connect
            connector = self.getConnector(auto_login)
            data = connector.diviFeatchData()
            if data is not None:
                self.tvData.model().addData( *data )
                self.setLogginStatus(True)
                self.getLoadedDiviLayers()
                return
        QSettings().remove('divi/token')
        self.setLogginStatus(False)
    
    def setLogginStatus(self, logged):
        if logged:
            self.lblStatus.setText(self.tr('Zalogowany: %s' % self.user))
            self.btnConnect.setText(self.trUtf8(u'Rozłącz'))
            self.btnConnect.setChecked(True)
        else:
            self.tvData.model().removeAll()
            self.lblStatus.setText(self.tr('Niezalogowany'))
            self.btnConnect.setText(self.trUtf8(u'Połącz'))
            self.btnConnect.setChecked(False)
            self.token = None
        QgsMessageLog.logMessage(str(self.token), 'DIVI')
    
    def setUserData(self, user, token):
        self.user = user
        self.token = token
        if token:
            self.setLogginStatus(True)
    
    def getLoadedDiviLayers(self):
        layers = [ layer for layer in QgsMapLayerRegistry.instance().mapLayers().itervalues() if layer.customProperty('DiviId') is not None ]
        for layer in layers:
            layerItem = self.findLayerItem(layer.customProperty('DiviId'))
            if layerItem is not None:
                layerItem.items.append(layer)
    
    #SLOTS
    
    def dblClick(self, index):
        item = index.internalPointer()
        if isinstance(item, LayerItem):
            msgBar = ProgressMessageBar(self.iface, self.tr(u"Pobieranie warstwy '%s'...")%item.name)
            msgBar.progress.setValue(10)
            connector = self.getConnector(progress=msgBar.progress, progressMin=10, progressMax=40)
            data = connector.diviGetLayerFeatures(item.id)
            if data:
                item.items.extend( self.addLayer(data['features'], item, progress=msgBar.progress) )
            msgBar.progress.setValue(100)
            msgBar.close()
        elif isinstance(item, TableItem):
            self.iface.messageBar().pushMessage('DIVI',
                self.trUtf8(u'Aby dodać tabelę musisz posiadać QGIS w wersji 2.14 lub nowszej.'),
                QgsMessageBar.CRITICAL,
                duration = 3
            )
    
    def showMenu(self, point):
        index = self.tvData.indexAt(point)
        item = index.internalPointer()
        menu = QtGui.QMenu(self)
        if isinstance(item, LayerItem):
            #Layer menu
            menu.addAction(self.trUtf8(u'Dodaj warstwę'), lambda: self.dblClick(index))
        menu.popup(self.tvData.viewport().mapToGlobal(point))
    
    def layersRemoved(self, layers):
        removed_ids = set([])
        for lid in layers:
            layer = QgsMapLayerRegistry.instance().mapLayer(lid)
            layerItem = self.findLayerItem(layer.customProperty('DiviId'))
            if layerItem is not None and layer in layerItem.items:
                layerItem.items.remove(layer)
    
    #OTHERS
    
    def addLayer(self, features, layer, progress=None):
        #Layers have CRS==4326
        definition = '?crs=epsg:4326'
        #Create temp layers for point, linestring and polygon geometry types
        points = QgsVectorLayer("MultiPoint"+definition, layer.name, "memory")
        lines = QgsVectorLayer("MultiLineString"+definition, layer.name, "memory")
        polygons = QgsVectorLayer("MultiPolygon"+definition, layer.name, "memory")
        return addFeatures(layer.id, features, fields=getFields(layer.fields),
            points=points, lines=lines, polygons=polygons,
            progress=progress, progressMin=50, progressMax=100)
    
    def findLayerItem(self, lid):
        if lid is None:
            return
        layers = self.tvData.model().match(
            self.tvData.model().index(0,0),
            Qt.UserRole,
            'layer@%s' % lid,
            1,
            Qt.MatchRecursive
        )
        if layers:
            return layers[0].internalPointer()
