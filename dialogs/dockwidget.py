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
from functools import partial

from PyQt4 import QtGui, uic
from PyQt4.QtCore import pyqtSignal, QSettings, Qt, QRegExp
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsVectorLayer
from qgis.gui import QgsMessageBar
from ..utils.connector import DiviConnector
from ..utils.model import DiviModel, LeafFilterProxyModel, LayerItem, TableItem
from ..utils.widgets import ProgressMessageBar

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dockwidget.ui'))


class DiviPluginDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, plugin, parent=None):
        """Constructor."""
        super(DiviPluginDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.plugin = plugin
        self.iface = plugin.iface
        self.token = QSettings().value('divi/token', None)
        self.user = QSettings().value('divi/email', None)
        self.setupUi(self)
        proxyModel = LeafFilterProxyModel()
        proxyModel.setSourceModel( DiviModel() )
        self.tvData.setModel( proxyModel )
        self.setLogginStatus(bool(self.token))
        if self.token:
            self.diviConnection(True, auto_login=False)
        #Signals
        self.btnConnect.clicked.connect(self.diviConnection)
        self.eSearch.textChanged.connect(self.searchData)
        self.tvData.doubleClicked.connect(self.dblClick)
        self.tvData.customContextMenuRequested.connect(self.showMenu)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect( self.layersRemoved )
    
    def getConnector(self, auto_login=True):
        connector = DiviConnector(iface=self.iface, auto_login=auto_login)
        connector.diviLogged.connect(self.setUserData)
        return connector
    
    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
    
    def diviConnection(self, checked, auto_login=True):
        model = self.tvData.model().sourceModel()
        if checked:
            #Connect
            model.showLoading()
            connector = self.getConnector(auto_login)
            data = connector.diviFeatchData()
            if data is not None:
                model.addData( *data )
                self.setLogginStatus(True)
                self.getLoadedDiviLayers()
                return
            else:
                model.removeAll()
        QSettings().remove('divi/token')
        QSettings().remove('divi/id')
        QSettings().remove('divi/status')
        self.setLogginStatus(False)
    
    def setLogginStatus(self, logged):
        if logged:
            self.lblStatus.setText(self.tr('Zalogowany: %s' % self.user))
            self.btnConnect.setText(self.trUtf8(u'Rozłącz'))
            self.btnConnect.setChecked(True)
        else:
            self.tvData.model().sourceModel().removeAll()
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
    
    def getLoadedDiviLayers(self, layers=None):
        if layers is None:
            layers = [ layer for layer in QgsMapLayerRegistry.instance().mapLayers().itervalues() if layer.customProperty('DiviId') is not None ]
        for layer in layers:
            layerItem = self.findLayerItem(layer.customProperty('DiviId'))
            if layerItem is not None:
                layerItem.items.append(layer)
    
    #SLOTS
    
    def dblClick(self, index):
        if not self.plugin.setLoading(True):
            return
        item = index.data(role=Qt.UserRole)
        if isinstance(item, LayerItem):
            self.plugin.msgBar = ProgressMessageBar(self.iface, self.tr(u"Pobieranie warstwy '%s'...")%item.name)
            self.plugin.msgBar.setValue(10)
            connector = self.getConnector()
            connector.downloadingProgress.connect(self.plugin.updateDownloadProgress)
            data = connector.diviGetLayerFeatures(item.id)
            if data:
                permissions = connector.getUserLayerPermissions(item.id)
                self.plugin.msgBar.setBoundries(50, 50)
                item.items.extend( self.plugin.addLayer(data['features'], item, permissions) )
            self.plugin.msgBar.setValue(100)
            self.plugin.msgBar.close()
            self.plugin.msgBar = None
        elif isinstance(item, TableItem):
            self.iface.messageBar().pushMessage('DIVI',
                #self.trUtf8(u'Aby dodać tabelę musisz posiadać QGIS w wersji 2.14 lub nowszej.'),
                self.trUtf8(u'W aktualnej wersji nie można wczytywać tabel DIVI.'),
                QgsMessageBar.CRITICAL,
                duration = 3
            )
        self.tvData.model().sourceModel().dataChanged.emit(index, index)
        self.plugin.setLoading(False)
    
    def refreshData(self, item):
        layers = item.items[:]
        if any( l.isEditable() for l in layers ):
            self.iface.messageBar().pushMessage('DIVI',
                self.trUtf8(u'Jedna z powiązanych warstw jest w trybie edycji. Zakończ edycję aby kontynuować.'),
                self.iface.messageBar().CRITICAL,
                duration = 3
            )
            return
        for lyr in layers:
            lyr.dataProvider().deleteFeatures(lyr.allFeatureIds())
            #We must disconnect signal because loadLayer will connect them again
            lyr.beforeCommitChanges.disconnect()
            lyr.committedFeaturesAdded.disconnect()
            layer_meta = self.plugin.loadLayer(lyr)
            lyr.triggerRepaint()
        item.items = layers[:]
        item.updateData(layer_meta)
    
    def showMenu(self, point):
        index = self.tvData.indexAt(point)
        item = index.data(role=Qt.UserRole)
        menu = QtGui.QMenu(self)
        if isinstance(item, LayerItem):
            #Layer menu
            menu.addAction(self.trUtf8(u'Dodaj warstwę'), lambda: self.dblClick(index))
            open_as_menu = menu.addMenu(self.trUtf8(u"Dodaj warstwę jako..."))
            load_layer_as = partial(self.plugin.loadLayerType, item=item)
            open_as_menu.addAction(self.tr('Punkty'), lambda: load_layer_as(geom_type='MultiPoint'))
            open_as_menu.addAction(self.tr('Linie'), lambda: load_layer_as(geom_type='MultiLineString'))
            open_as_menu.addAction(self.tr('Poligony'), lambda: load_layer_as(geom_type='MultiPolygon'))
            menu.addAction(self.trUtf8(u'Zmień nazwę warstwy...'), lambda: self.editLayerName(index))
            if item.items:
                menu.addAction(self.trUtf8(u'Odśwież dane'), lambda: self.refreshData(item))
        menu.popup(self.tvData.viewport().mapToGlobal(point))
    
    def layersRemoved(self, layers):
        removed_ids = set([])
        for lid in layers:
            layer = QgsMapLayerRegistry.instance().mapLayer(lid)
            QgsMessageLog.logMessage(self.trUtf8('Usuwanie warstwy %s')%layer.name(), 'DIVI')
            layerItem = self.findLayerItem(layer.customProperty('DiviId'))
            if layerItem is not None and layer in layerItem.items:
                layerItem.items.remove(layer)
                if not layer.isReadOnly():
                    layer.beforeCommitChanges.disconnect(self.plugin.onLayerCommit)
                    layer.committedFeaturesAdded.disconnect(self.plugin.onFeaturesAdded)
    
    def searchData(self, text):
        self.tvData.model().setFilterRegExp(QRegExp(text, Qt.CaseInsensitive, QRegExp.FixedString))
        if text:
            self.tvData.expandAll()
        else:
            self.tvData.collapseAll()
    
    def editLayerName(self, index):
        item = index.data(role=Qt.UserRole)
        name, status = QtGui.QInputDialog.getText(self, self.trUtf8(u'Zmień nazwę'),
            self.trUtf8(u'Podaj nową nazwę dla warstwy %s') % item.name,
            text = item.name)
        if status and name != item.name:
            result = self.editLayerMetadata(item.id, {'name':name})
            if result['layer']['name'] == name:
                self.iface.messageBar().pushMessage('DIVI',
                    self.trUtf8(u'Zmieniono nazwę warstwy %s na %s.') % (item.name, name),
                    duration = 3
                )
                item.name = name
                self.tvData.model().sourceModel().dataChanged.emit(index, index)
            else:
                self.iface.messageBar().pushMessage('DIVI',
                    self.trUtf8(u'Wystąpił błąd podczas zmiany nazwy.'),
                    self.iface.messageBar().CRITICAL,
                    duration = 3
                )
    
    def editLayerMetadata(self, layerid, data):
        connector = self.getConnector()
        return connector.updateLayer(layerid, data)
    
    #OTHERS
    
    def findLayerItem(self, lid):
        if lid is None:
            return
        model = self.tvData.model().sourceModel()
        layers = model.match(
            model.index(0,0),
            Qt.UserRole+1,
            'layer@%s' % lid,
            1,
            Qt.MatchRecursive
        )
        if layers:
            return layers[0].data(role=Qt.UserRole)
