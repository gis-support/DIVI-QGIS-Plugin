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

from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal, QSettings, Qt, QRegExp
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsVectorLayer, QGis,\
    QgsApplication, QgsRasterLayer, QgsRectangle, QgsCoordinateReferenceSystem,\
    QgsCoordinateTransform
from PyQt4.QtGui import QDockWidget, QInputDialog, QMenu, QToolButton, QMessageBox
from qgis.gui import QgsMessageBar, QgsFilterLineEdit
from ..config import *
from ..utils.connector import DiviConnector
from ..models.DiviModel import DiviModel, DiviProxyModel, LayerItem, TableItem, \
    ProjectItem, VectorItem, RasterItem, WmsItem, BasemapItem
from ..widgets.ProgressMessageBar import ProgressMessageBar
from ..utils.commons import Cache
from ..utils.files import getSavePath

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dockwidget.ui'))


class DiviPluginDockWidget(QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    transform2mercator = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem('EPSG:4326'),
            QgsCoordinateReferenceSystem('EPSG:3857')
        )

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
        self.token = QSettings().value('%s/token' % CONFIG_NAME, None)
        self.user = QSettings().value('%s/email' % CONFIG_NAME, None)
        self.setupUi(self)
        self.initGui()
        proxyModel = DiviProxyModel()
        proxyModel.setSourceModel( DiviModel() )
        proxyModel.setDynamicSortFilter( True )
        self.tvData.setModel( proxyModel )
        self.tvData.setSortingEnabled(True)
        self.setLogginStatus(bool(self.token))
        #Signals
        self.btnConnect.clicked.connect(self.diviConnection)
        self.eSearch.textChanged.connect(self.searchData)
        self.tvData.activated.connect(self.addLayer)
        self.tvData.customContextMenuRequested.connect(self.showMenu)
        self.tvData.selectionModel().currentChanged.connect(self.treeSelectionChanged)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect( self.layersRemoved )
        self.gbFilters.collapsedStateChanged.connect(self.toggleFilters)
        self.cbVectors.stateChanged.connect(self.setSearchFilter)
        self.cbTables.stateChanged.connect(self.setSearchFilter)
        self.cbRasters.stateChanged.connect(self.setSearchFilter)
        self.cbWms.stateChanged.connect(self.setSearchFilter)
        self.cbBasemaps.stateChanged.connect(self.setSearchFilter)
        self.setSearchFilter(None)
    
    def initGui(self):
        self.eSearch = QgsFilterLineEdit(self.dockWidgetContents)
        self.eSearch.setObjectName(u"eSearch")
        self.eSearch.setPlaceholderText(self.tr("Search..."))
        self.editLayout.addWidget(self.eSearch)
        #Toolbar
        self.btnAddLayer.setIcon( QgsApplication.getThemeIcon('/mActionAddMap.png') )
        menu = QMenu()
        menu.aboutToShow.connect(self.addMenuShow)
        self.btnAddLayer.setMenu(menu)
        self.btnAddLayer.clicked.connect( self.addItems )
        self.btnRefresh.clicked.connect(lambda checked: self.refreshItems( self.tvData.selectedIndexes()[0] if self.tvData.selectedIndexes() else None ))
        self.btnRefresh.setIcon( QgsApplication.getThemeIcon('/mActionDraw.svg') )
        #Filters
        settings = QSettings()
        self.gbFilters.setCollapsed( not settings.value( '{}/filters/filters'.format(CONFIG_NAME), False, bool ) )
        self.cbVectors.setChecked( settings.value( '{}/filters/vectors'.format(CONFIG_NAME), True, bool ) )
        self.cbTables.setChecked( settings.value( '{}/filters/tables'.format(CONFIG_NAME), True, bool ) )
        self.cbRasters.setChecked( settings.value( '{}/filters/rasters'.format(CONFIG_NAME), True, bool ) )
        self.cbWms.setChecked( settings.value( '{}/filters/wms'.format(CONFIG_NAME), True, bool ) )
        self.cbBasemaps.setChecked( settings.value( '{}/filters/basmeaps'.format(CONFIG_NAME), True, bool ) )
    
    def getConnector(self, auto_login=True):
        connector = DiviConnector(iface=self.iface, auto_login=auto_login)
        connector.diviLogged.connect(self.setUserData)
        return connector
    
    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
    
    def diviConnection(self, checked, auto_login=True):
        model = self.tvData.model().sourceModel()
        connector = self.getConnector(auto_login)
        if checked:
            #Connect
            model.showLoading()
            data = connector.diviFeatchData()
            if data is not None:
                model.addData( *data )
                self.setLogginStatus(True)
                items = self.getLoadedDiviLayers()
                #Refresh data after connect
                for item in items:
                    self.refreshData( item )
                return
            else:
                model.removeAll()
        else:
            #Disconnect
            layers = [ layer for layer in QgsMapLayerRegistry.instance().mapLayers().itervalues() if layer.customProperty('DiviId') is not None ]
            if any(layer.isModified() for layer in layers):
                result = QMessageBox.question(None, self.tr('Edited layers'), 
                    self.tr('Some layers are modified. You need to save changes or rollback to continue. Do you want to revert all edits?'),
                    QMessageBox.Yes | QMessageBox.No)
                if result==QMessageBox.No:
                    self.btnConnect.setChecked(True)
                    return
            for layer in layers:
                if layer.isEditable():
                    layer.rollBack()
            connector.diviLogout()
            self.btnAddLayer.setEnabled(False)
            self.btnRefresh.setEnabled(False)
        settings = QSettings()
        settings.remove('%s/token' % CONFIG_NAME)
        settings.remove('%s/id' % CONFIG_NAME)
        settings.remove('%s/status' % CONFIG_NAME)
        self.setLogginStatus(False)
    
    def setLogginStatus(self, logged):
        if logged:
            self.setWindowTitle( 'DIVI QGIS Plugin - %s' % self.user )
            self.btnConnect.setText(self.tr('Disconnect'))
            self.btnConnect.setChecked(True)
        else:
            self.tvData.model().sourceModel().removeAll()
            self.setWindowTitle( 'DIVI QGIS Plugin' )
            self.btnConnect.setText(self.tr('Connect'))
            self.btnConnect.setChecked(False)
            self.token = None
        self.plugin.setEnabled( logged )
        QgsMessageLog.logMessage(str(self.token), 'DIVI')
    
    def setUserData(self, user, token):
        self.user = user
        self.token = token
        if token:
            self.setLogginStatus(True)
    
    def getLoadedDiviLayers(self, layers=None):
        if layers is None:
            layers = [ layer for layer in QgsMapLayerRegistry.instance().mapLayers().itervalues() if layer.customProperty('DiviId') is not None ]
        model = self.tvData.model().sourceModel()
        items = set()
        for layer in layers:
            divi_id = layer.customProperty('DiviId')
            item_type = self.plugin.getItemType(layer)
            layerIndex = model.findItem(divi_id, item_type, True)
            if layerIndex is not None:
                layerItem = layerIndex.data(role=Qt.UserRole)
                items.add(layerItem)
                if layer not in layerItem.items:
                    fields = [] if isinstance(layer, QgsRasterLayer) else layerItem.fields
                    layerItem.items.append(layer)
                    model.dataChanged.emit(layerIndex, layerIndex)
                    if isinstance(layerItem, RasterItem):
                        self.plugin.updateRasterToken( layer, layerItem.getUri(self.token) )
        return items
    
    #SLOTS
    
    def addMenuShow(self):
        menu = self.sender()
        menu.clear()
        indexes = self.tvData.selectedIndexes()
        if not indexes:
            return
        item = indexes[0].data(Qt.UserRole)
        add_text = self.tr('Add layer') if isinstance(item, LayerItem) else self.tr(u'Add all layers from project')
        add = menu.addAction(QgsApplication.getThemeIcon('/mActionAddMap.png'), add_text, lambda: self.addLayer(indexes[0]))
        f = add.font()
        f.setBold(True)
        add.setFont(f)
        if not isinstance(item, VectorItem):
            return
        sep = menu.addSeparator()
        sep.setText(self.tr('Add as...'))
        sep.setEnabled(False)
        load_layer_as = partial(self.plugin.loadLayerType, item=item)
        menu.addAction(QgsApplication.getThemeIcon('/mIconPointLayer.svg'), self.tr('Points'), lambda: load_layer_as(geom_type='MultiPoint'))
        menu.addAction(QgsApplication.getThemeIcon('/mIconLineLayer.svg'), self.tr('Linestring'), lambda: load_layer_as(geom_type='MultiLineString'))
        menu.addAction(QgsApplication.getThemeIcon('/mIconPolygonLayer.svg'), self.tr('Polygons'), lambda: load_layer_as(geom_type='MultiPolygon'))
    
    def treeSelectionChanged(self, new, old):
        item = new.data(Qt.UserRole)
        self.btnAddLayer.setEnabled( isinstance(item, (LayerItem, ProjectItem)) )
        self.btnRefresh.setEnabled( (not isinstance(item, LayerItem)) or (isinstance(item, TableItem)) )
    
    def addItems(self):
        indexes = self.tvData.selectedIndexes()
        if not indexes:
            return
        index = indexes[0]
        item = index.data(Qt.UserRole)
        if isinstance(item, LayerItem):
            self.addLayer(index)
        elif isinstance(item, ProjectItem):
            self.addProjectData(index)
    
    def addLayer(self, index, old=None):
        item = index.data(role=Qt.UserRole)
        if not isinstance(item, LayerItem):
            return
        if not self.plugin.setLoading(True):
            return
        addedData = []
        if isinstance(item, VectorItem):
            connector = self.getConnector()
            self.plugin.msgBar = ProgressMessageBar(self.iface, self.tr("Downloading layer '%s'...")%item.name, connector=connector)
            self.plugin.msgBar.setValue(10)
            connector.downloadingProgress.connect(self.plugin.updateDownloadProgress)
            data = connector.diviGetLayerFeatures(item.id)
            layers = []
            if data:
                permissions = connector.getUserPermission(item.id, 'layer')
                self.plugin.msgBar.setBoundries(50, 50)
                #Disable rendering for changing symbology
                self.iface.mapCanvas().setRenderFlag(False)
                layers = self.plugin.addLayer(data['features'], item, permissions)
                for layer in layers:
                    #Set symbols based on layer geometry type
                    item.setQgisStyle(layer)
                    self.iface.legendInterface().refreshLayerSymbology(layer)
                self.iface.mapCanvas().setRenderFlag(True)
                addedData.extend( layers )
                item.items.extend( addedData )
            self.plugin.msgBar.setValue(100)
            aborted = self.plugin.msgBar.aborted
            self.plugin.msgBar.close()
            self.plugin.msgBar = None
            if aborted:
                print 'Aborted'
            elif not layers:
                #User can select geometry type in message bar
                widget = self.iface.messageBar().createMessage(
                    self.tr("Warning"),
                    self.tr(u"Layer '%s' is empty. To open it in QGIS you need to select geometry type.") % item.name
                )
                button = QToolButton(widget)
                button.setText(self.tr("Add layer as..."))
                button.setPopupMode(QToolButton.InstantPopup)
                menu = QMenu(button)
                load_layer_as = partial(self.plugin.loadLayerType, item=item)
                menu.addAction(QgsApplication.getThemeIcon('/mIconPointLayer.svg'), self.tr('Points'), lambda: load_layer_as(geom_type='MultiPoint'))
                menu.addAction(QgsApplication.getThemeIcon('/mIconLineLayer.svg'), self.tr('Linestring'), lambda: load_layer_as(geom_type='MultiLineString'))
                menu.addAction(QgsApplication.getThemeIcon('/mIconPolygonLayer.svg'), self.tr('Polygons'), lambda: load_layer_as(geom_type='MultiPolygon'))
                button.setMenu( menu )
                widget.layout().addWidget(button)
                self.iface.messageBar().pushWidget(widget, QgsMessageBar.WARNING)

        elif isinstance(item, TableItem):
            if QGis.QGIS_VERSION_INT < 21400:
                self.iface.messageBar().pushMessage('DIVI',
                    self.tr(u'QGIS 2.14 or later is required for loading DIVI tables.'),
                    QgsMessageBar.CRITICAL,
                    duration = 3
                )
            else:
                self.plugin.msgBar = ProgressMessageBar(self.iface, self.tr("Downloading table '%s'...")%item.name)
                self.plugin.msgBar.setValue(10)
                connector = self.getConnector()
                connector.downloadingProgress.connect(self.plugin.updateDownloadProgress)
                data = connector.diviGetTableRecords(item.id)
                if data:
                    permissions = connector.getUserPermission(item.id, 'table')
                    self.plugin.msgBar.setBoundries(50, 50)
                    addedData.append( self.plugin.addTable(data['header'], data['data'], item, permissions) )
                    item.items.extend( addedData )
                self.plugin.msgBar.setValue(100)
                self.plugin.msgBar.close()
                self.plugin.msgBar = None
        elif isinstance(item, RasterItem):
            if QGis.QGIS_VERSION_INT < 21800:
                self.iface.messageBar().pushMessage('DIVI',
                    self.tr(u'QGIS 2.18 or later is required for loading DIVI rasters.'),
                    QgsMessageBar.CRITICAL,
                    duration = 3
                )
            else:
                uri = item.getUri(self.token)
                QgsMessageLog.logMessage( uri, 'DIVI')
                r = QgsRasterLayer(uri, item.name, 'wms')
                r.setCustomProperty('DiviId', item.id)
                if item.extent is not None:
                    #Set extent for raster layer
                    bbox = self.transform2mercator.transformBoundingBox( QgsRectangle(
                            item.extent['st_xmin'],
                            item.extent['st_ymin'],
                            item.extent['st_xmax'],
                            item.extent['st_ymax']
                        ))
                    r.setExtent( bbox )
                addedData.append( r )
                item.items.extend( addedData )
                QgsMapLayerRegistry.instance().addMapLayer(r)
        elif isinstance(item, WmsItem):
            uri = item.getUri()
            QgsMessageLog.logMessage( uri, 'DIVI')
            r = QgsRasterLayer(uri, item.name, 'wms')
            r.setCustomProperty('DiviId', item.id)
            addedData.append( r )
            item.items.extend( addedData )
            QgsMapLayerRegistry.instance().addMapLayer(r)
        elif isinstance(item, BasemapItem):
            uri = item.getUri()
            QgsMessageLog.logMessage( uri, 'DIVI')
            r = QgsRasterLayer(uri, item.name, 'wms')
            r.setCustomProperty('DiviId', item.id)
            addedData.append( r )
            item.items.extend( addedData )
            QgsMapLayerRegistry.instance().addMapLayer(r)
        else:
            return
        index.model().dataChanged.emit(index.parent().parent(), index)
        self.plugin.setLoading(False)
        return addedData
    
    def refreshData(self, item):
        layers = item.items[:]
        if any( l.isEditable() for l in layers ):
            self.iface.messageBar().pushMessage('DIVI',
                self.tr(u'One of related layers is in edit mode. End edit mode of that layer to continue.'),
                self.iface.messageBar().CRITICAL,
                duration = 3
            )
            return
        with Cache(self.plugin):
            for lyr in layers:
                lyr.dataProvider().deleteFeatures(lyr.allFeatureIds())
                try:
                    self.plugin.unregisterLayer(lyr)
                except TypeError:
                    pass
                layer_meta = self.plugin.loadLayer(lyr)
                lyr.triggerRepaint()
        item.items = layers[:]
        item.updateData(layer_meta)
    
    def showMenu(self, point):
        index = self.tvData.indexAt(point)
        item = index.data(role=Qt.UserRole)
        menu = QMenu(self)
        if isinstance(item, LayerItem):
            #Layer menu
            if isinstance(item, TableItem):
                menu.addAction(QgsApplication.getThemeIcon('/mActionAddMap.png'), self.tr('Add layer'), lambda: self.addLayer(index))
                if type(item) is VectorItem:
                    open_as_menu = menu.addMenu(QgsApplication.getThemeIcon('/mActionAddOgrLayer.svg'), self.tr("Add layer as..."))
                    load_layer_as = partial(self.plugin.loadLayerType, item=item)
                    open_as_menu.addAction(QgsApplication.getThemeIcon('/mIconPointLayer.svg'), self.tr('Points'), lambda: load_layer_as(geom_type='MultiPoint'))
                    open_as_menu.addAction(QgsApplication.getThemeIcon('/mIconLineLayer.svg'), self.tr('Linestring'), lambda: load_layer_as(geom_type='MultiLineString'))
                    open_as_menu.addAction(QgsApplication.getThemeIcon('/mIconPolygonLayer.svg'), self.tr('Polygons'), lambda: load_layer_as(geom_type='MultiPolygon'))
            elif isinstance(item, RasterItem):
                menu.addAction(QgsApplication.getThemeIcon('/mActionAddMap.png'), self.tr('Download raster'), lambda: self.downloadRaster(index))
            menu.addAction(QgsApplication.getThemeIcon('/mActionToggleEditing.svg'), self.tr('Change layer name...'), lambda: self.editLayerName(index))
            if item.items:
                menu.addAction(QgsApplication.getThemeIcon('/mActionDraw.svg'), self.tr('Reload data'), lambda: self.refreshData(item))
        elif isinstance(item, ProjectItem):
            menu.addAction(QgsApplication.getThemeIcon('/mActionAddGroup.png'), self.tr(u'Add all layers from project'), lambda: self.addProjectData(index))
            menu.addAction(QgsApplication.getThemeIcon('/mActionDraw.svg'), self.tr(u'Refresh items'), lambda: self.refreshItems(index))
        menu.popup(self.tvData.viewport().mapToGlobal(point))
    
    def layersRemoved(self, layers):
        removed_ids = set([])
        model = self.tvData.model().sourceModel()
        for lid in layers:
            layer = QgsMapLayerRegistry.instance().mapLayer(lid)
            divi_id = layer.customProperty('DiviId')
            if divi_id is None:
                continue
            QgsMessageLog.logMessage(self.tr('Removing layer %s')%layer.name(), 'DIVI')
            item_type = self.plugin.getItemType(layer)
            layerIndex = model.findItem(divi_id, item_type, True)
            if layerIndex is None:
                continue
            layerItem = layerIndex.data(role=Qt.UserRole)
            if layer in layerItem.items:
                layerItem.items.remove(layer)
                self.plugin.unregisterLayer(layer)
                model.dataChanged.emit(layerIndex, layerIndex)
    
    def searchData(self, text):
        self.tvData.model().setFilterRegExp(QRegExp(text, Qt.CaseInsensitive, QRegExp.FixedString))
        if text:
            self.tvData.expandAll()
        else:
            self.tvData.collapseAll()
    
    def setSearchFilter(self, value):
        settings = QSettings()
        settings.setValue( '{}/filters/vectors'.format(CONFIG_NAME), self.cbVectors.isChecked() )
        settings.setValue( '{}/filters/tables'.format(CONFIG_NAME), self.cbTables.isChecked() )
        settings.setValue( '{}/filters/rasters'.format(CONFIG_NAME), self.cbRasters.isChecked() )
        settings.setValue( '{}/filters/wms'.format(CONFIG_NAME), self.cbWms.isChecked() )
        settings.setValue( '{}/filters/basmeaps'.format(CONFIG_NAME), self.cbBasemaps.isChecked() )
        filters = ['loading']
        if self.cbVectors.isChecked():
            filters.append('vector')
        if self.cbTables.isChecked():
            filters.append('table')
        if self.cbRasters.isChecked():
            filters.append('raster')
        if self.cbWms.isChecked():
            filters.append('wms')
        if self.cbBasemaps.isChecked():
            filters.append('basemap')
        self.tvData.model().types = filters
        self.tvData.model().invalidateFilter()
    
    def toggleFilters(self, collapsed):
        print collapsed
        QSettings().setValue( '{}/filters/filters'.format(CONFIG_NAME), not collapsed )
    
    def editLayerName(self, index):
        item = index.data(role=Qt.UserRole)
        name, status = QInputDialog.getText(self, self.tr('Change name'),
            self.tr('Enter new layer name for %s') % item.name,
            text = item.name)
        if status and name != item.name:
            result = self.editLayerMetadata(item, {'name':name})
            if result['layer']['name'] == name:
                self.iface.messageBar().pushMessage('DIVI',
                    self.tr('Name of layer %s was changed to %s.') % (item.name, name),
                    duration = 3
                )
                item.name = name
                index.model().dataChanged.emit(index, index)
            else:
                self.iface.messageBar().pushMessage('DIVI',
                    self.tr('Error occured while changing name.'),
                    self.iface.messageBar().CRITICAL,
                    duration = 3
                )
    
    def editLayerMetadata(self, item, data):
        connector = self.getConnector()
        if type(item) is TableItem:
            item_type = 'table'
        else:
            item_type = 'vector'
        return connector.updateLayer(item.id, data, item_type=item_type)
    
    def addProjectData(self, index):
        item = index.data( role=Qt.UserRole )
        layers = []
        for i, data in enumerate(item.childItems):
            if isinstance(data, LayerItem):
                layers.extend( self.addLayer( index.child(i, 0) ) )
        if layers:
            idx = self.iface.legendInterface().addGroup(item.name, True)
            for layer in reversed(layers):
                self.iface.legendInterface().moveLayer(layer, idx)
    
    def refreshItems(self, index):
        if index is None:
            return
        index = self.tvData.model().mapToSource(index)
        item = index.data( role=Qt.UserRole )
        if isinstance(item, TableItem):
            self.plugin.loadLayers(item.items)
            return
        elif isinstance(item, LayerItem):
            return
        connector = self.getConnector()
        model = self.tvData.model().sourceModel()
        self.unregisterLayers(item)
        model.removeRows(0, item.childCount(),index)
        layers, tables = connector.diviGetProjectItems(projectid=item.id)
        model.addProjectItems(item, layers, tables)
        self.getLoadedDiviLayers()
    
    def downloadRaster(self, index):
        item = index.data(Qt.UserRole)
        filePath = getSavePath( '%s.tiff' % item.name )
        if filePath is None:
            return
        connector = self.getConnector()
        fileData = connector.downloadRaster( item.id )
        with open(filePath, 'wb') as f:
                f.write(fileData)
    
    def unregisterLayers(self, item):
        for child in item.childItems:
            for layer in child.items:
                self.plugin.unregisterLayer(layer)
