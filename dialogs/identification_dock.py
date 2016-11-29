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
from PyQt4.QtGui import QDockWidget, QIcon, QFileDialog, QInputDialog, \
    QMessageBox, QMenu
import os.path as op
from ..models.ActivitiesModel import ActivitiesModel, ActivitiesProxyModel, \
    AttachmentItem, ActivitiesItem, RasterItem, HTMLDelegate
from ..utils.files import readFile
import os.path as op

FORM_CLASS, _ = uic.loadUiType(op.join(
    op.dirname(__file__), 'identification_dock.ui'))

class DiviPluginIdentificationPanel(QDockWidget, FORM_CLASS):
    def __init__(self, plugin, parent=None):
        """Constructor."""
        super(DiviPluginIdentificationPanel, self).__init__(parent)
        self.plugin = plugin
        self.setupUi(self)
        self.initGui()
    
    def initGui(self):
        #Model
        proxyModel = ActivitiesProxyModel()
        proxyModel.setSourceModel( ActivitiesModel() )
        proxyModel.setDynamicSortFilter( True )
        self.tvIdentificationResult.setModel( proxyModel )
        self.tvIdentificationResult.setSortingEnabled(True)
        self.tvIdentificationResult.setItemDelegate(HTMLDelegate())
        #Toolbar
        self.btnAddAttachment.setIcon( QIcon(':/plugins/DiviPlugin/images/attachment_add.png') )
        self.btnRemoveAttachment.setIcon( QIcon(':/plugins/DiviPlugin/images/attachment_remove.png') )
        self.btnDownloadAttachment.setIcon( QIcon(':/plugins/DiviPlugin/images/attachment_download.png') )
        self.btnAddComment.setIcon( QIcon(':/plugins/DiviPlugin/images/comment_add.png') )
        menu = QMenu()
        menu.aboutToShow.connect(self.downloadMenuShow)
        self.btnDownloadAttachment.setMenu(menu)
        #Signals
        self.tvIdentificationResult.activated.connect( self.itemActivated )
        self.tvIdentificationResult.selectionModel().currentChanged.connect(self.treeSelectionChanged)
        self.tvIdentificationResult.collapsed.connect( lambda index: self.itemViewChanged(index, False) )
        self.tvIdentificationResult.expanded.connect( lambda index: self.itemViewChanged(index, True) )
        self.tvIdentificationResult.model().sourceModel().layerTypeChanged.connect( lambda layerType: self.setToolbarEnabled(layerType=='vector') )
        self.tvIdentificationResult.model().sourceModel().expand.connect( 
            lambda index: self.tvIdentificationResult.expand( self.tvIdentificationResult.model().mapFromSource( index ) ) )
        self.btnDownloadAttachment.clicked.connect( self.downloadFiles )
        self.btnAddAttachment.clicked.connect( self.addAttachment )
        self.btnRemoveAttachment.clicked.connect( self.removeAttachment )
        self.btnAddComment.clicked.connect( self.addComment )
    
    def itemActivated(self, index):
        item = index.data(Qt.UserRole)
        if isinstance(item, AttachmentItem):
            self.saveFile( item.name )
    
    def treeSelectionChanged(self, new, old):
        item = new.data(Qt.UserRole)
        if not item:
            return
        if isinstance(item, RasterItem) or item.type=='raster':
            self.setToolbarEnabled( False )
            self.btnRemoveAttachment.setEnabled( False )
            return
        self.btnRemoveAttachment.setEnabled( isinstance(item, AttachmentItem) )
    
    def setToolbarEnabled(self, enabled):
        self.btnAddAttachment.setEnabled( enabled )
        self.btnDownloadAttachment.setEnabled( enabled )
        self.btnAddComment.setEnabled( enabled )
    
    def downloadMenuShow(self):
        menu = self.sender()
        menu.clear()
        parent_item = self.tvIdentificationResult.model().sourceModel().findItem('attachments')
        if not parent_item.childCount():
            menu.addAction( self.tr('No attachments') ).setEnabled( False )
            return
        menu.addAction( self.tr('Download all'), lambda: self.saveFile( 'attachments.zip', True ) )
        menu.addSeparator()
        for child in parent_item.childItems:
            action = menu.addAction( child.icon, child.name, lambda: self.saveFile( self.sender().text() ) )
    
    def downloadFiles(self):
        indexes = self.tvIdentificationResult.selectedIndexes()
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
        featureid = self.tvIdentificationResult.model().sourceModel().currentFeature
        if allFiles:
            fileData = connector.getFiles( featureid )
        else:
            fileData = connector.getFile( featureid, fileName )
        with open(filePath, 'wb') as f:
                f.write(fileData)

    def addAttachment(self):
        settings = QSettings()
        defaultDir = settings.value('divi/last_dir', '')
        files = QFileDialog.getOpenFileNames(self, self.tr('Select attachment(s)'), defaultDir)
        if not files:
            return
        to_send = { op.basename(f):readFile(f) for f in files }
        connector = self.plugin.dockwidget.getConnector()
        fid = self.tvIdentificationResult.model().sourceModel().currentFeature
        if fid is None:
            return
        connector.sendAttachments( fid, to_send )
        attachments = connector.getAttachments( str(fid) )
        self.plugin.identifyTool.on_activities.emit( {'attachments':attachments.get('data', [])} )
    
    def removeAttachment(self):
        indexes = self.tvIdentificationResult.selectedIndexes()
        if not indexes:
            return
        item = indexes[0].data(Qt.UserRole)
        if not isinstance(item, AttachmentItem):
            return
        result = QMessageBox.question(self, 'DIVI QGIS Plugin', self.tr("Remove attachment '%s'?")%item.name,
            QMessageBox.Yes | QMessageBox.No)
        if result == QMessageBox.No:
            return
        fid = self.tvIdentificationResult.model().sourceModel().currentFeature
        if fid is None:
            return
        connector = self.plugin.dockwidget.getConnector()
        connector.removeAttachment( fid, item.name )
        attachments = connector.getAttachments( str(fid) )
        self.plugin.identifyTool.on_activities.emit( {'attachments':attachments.get('data', [])} )
    
    def addComment(self):
        text, _ = QInputDialog.getText(self, 'DIVI QGIS Plugin', self.tr('Add new comment'))
        if not text:
            return
        connector = self.plugin.dockwidget.getConnector()
        fid = self.tvIdentificationResult.model().sourceModel().currentFeature
        if fid is None:
            return
        connector.addComment(fid, text)
        comments = connector.getComments( str(fid) )
        self.plugin.identifyTool.on_activities.emit( {'comments':comments.get('data', [])} )
    
    def itemViewChanged(self, index, expanded):
        item = index.data(Qt.UserRole)
        if not isinstance(item, ActivitiesItem):
            return
        QSettings().setValue('divi/expanded/%s' % item.type, expanded)
