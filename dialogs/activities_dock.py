# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiviPluginActivitiesPanel
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

from PyQt4 import uic
from PyQt4.QtCore import Qt, QSettings
from PyQt4.QtGui import QDockWidget, QIcon, QFileDialog
import os.path as op
from ..models.ActivitiesModel import ActivitiesModel, ActivitiesProxyModel, \
    AttachmentItem

FORM_CLASS, _ = uic.loadUiType(op.join(
    op.dirname(__file__), 'activities_dock.ui'))

class DiviPluginActivitiesPanel(QDockWidget, FORM_CLASS):
    def __init__(self, plugin, parent=None):
        """Constructor."""
        super(DiviPluginActivitiesPanel, self).__init__(parent)
        self.plugin = plugin
        self.setupUi(self)
        self.initGui()
    
    def initGui(self):
        #Model
        proxyModel = ActivitiesProxyModel()
        proxyModel.setSourceModel( ActivitiesModel() )
        proxyModel.setDynamicSortFilter( True )
        self.tvActivities.setModel( proxyModel )
        self.tvActivities.setSortingEnabled(True)
        self.tvActivities.expandAll()
        #Toolbar
        self.btnAddAttachment.setIcon( QIcon(':/plugins/DiviPlugin/images/attachment_add.png') )
        self.btnRemoveAttachment.setIcon( QIcon(':/plugins/DiviPlugin/images/attachment_remove.png') )
        self.btnDownloadAttachment.setIcon( QIcon(':/plugins/DiviPlugin/images/attachment_download.png') )
        self.btnAddComment.setIcon( QIcon(':/plugins/DiviPlugin/images/comment_add.png') )
        #Signals
        self.tvActivities.activated.connect( self.itemActivated )
        self.tvActivities.selectionModel().currentChanged.connect(self.treeSelectionChanged)
        self.btnDownloadAttachment.clicked.connect( self.downloadFiles )
    
    def itemActivated(self, index):
        item = index.data(Qt.UserRole)
        if isinstance(item, AttachmentItem):
            self.saveFile( item.name )
    
    def treeSelectionChanged(self, new, old):
        item = new.data(Qt.UserRole)
        self.btnRemoveAttachment.setEnabled( isinstance(item, AttachmentItem) )
    
    def downloadFiles(self):
        indexes = self.tvActivities.selectedIndexes()
        if indexes:
            index = indexes[0]
            item = index.data(Qt.UserRole)
            if isinstance(item, AttachmentItem):
                return self.itemActivated(self, index)
        self.saveFile( 'attachments.zip', True )
    
    def saveFile(self, fileName, allFiles=False):
        ext = op.splitext(fileName)[-1]
        settings = QSettings()
        defaultDir = settings.value('divi/last_dir', '')
        defaultPath = op.join(defaultDir, fileName)
        filePath = QFileDialog.getSaveFileName(self, self.tr('Save file to...'),
            defaultPath, filter = ext)
        if not filePath:
            return
        settings.setValue('divi/last_dir', op.dirname(filePath))
        connector = self.plugin.dockwidget.getConnector()
        featureid = self.tvActivities.model().sourceModel().currentFeature
        if allFiles:
            fileData = connector.getFiles( featureid )
        else:
            fileData = connector.getFile( featureid, fileName )
        with open(filePath, 'wb') as f:
                f.write(fileData)
