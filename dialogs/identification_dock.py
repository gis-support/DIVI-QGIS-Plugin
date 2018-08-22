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

from PyQt5 import uic
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon, QImageReader
from PyQt5.QtWidgets import QMessageBox, QDockWidget, QFileDialog, QInputDialog, QMenu
import os.path as op
from .preview_dialog import DiviPluginPreviewDialog
from .history_dialog import DiviPluginHistoryDialog
from ..config import *
from ..models.ActivitiesModel import ActivitiesModel, ActivitiesProxyModel, \
    AttachmentItem, ActivitiesItem, RasterItem, HTMLDelegate, ChangeItem
from ..utils.files import readFile, getSavePath
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
        self.btnPreview.setIcon( QIcon(':/plugins/DiviPlugin/images/images.png') )
        self.btnHistory.setIcon( QIcon(':/plugins/DiviPlugin/images/book.png') )
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
        self.btnPreview.clicked.connect( self.showPreviewDialog )
        self.btnHistory.clicked.connect( self.showHistoryDialog )
        #GUI
        self.previewDialog = None
        self.historyDialog = None
    
    def setEnabled( self, enabled ):
        #Set widgets enable state by connection status
        self.fToolbar.setEnabled( enabled )
        self.tvIdentificationResult.setEnabled( enabled )
        if not enabled:
            self.tvIdentificationResult.model().sourceModel().clearItems()
    
    def setActiveFeature(self, fid):
        self.tvIdentificationResult.model().sourceModel().setCurrentFeature( fid )
        if fid is not None:
            self.setWindowTitle( self.tr('Feature informations: %d') % fid )
        else:
            self.setWindowTitle( self.tr('Feature informations') )
    
    def itemActivated(self, index):
        item = index.data(Qt.UserRole)
        if isinstance(item, AttachmentItem):
            self.saveFile( item.name )
        if isinstance(item, ChangeItem):
            self.showHistoryDialog()
    
    def treeSelectionChanged(self, new, old):
        item = new.data(Qt.UserRole)
        if not item:
            return
        if isinstance(item, RasterItem) or self.tvIdentificationResult.model().sourceModel().layerType=='raster':
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
                return self.itemActivated(index)
        self.saveFile( 'attachments.zip', True )
    
    def saveFile(self, fileName, allFiles=False):
        """ Save file to disk """
        featureid = self.tvIdentificationResult.model().sourceModel().currentFeature
        if featureid is None:
            return
        filePath = getSavePath( fileName )
        if filePath is None:
            return
        connector = self.plugin.dockwidget.getConnector()
        if allFiles:
            fileData = connector.getFiles( featureid )
        else:
            fileData = connector.getFile( featureid, fileName )
        
        filePath = str(filePath).split(',')[0].replace("'", "").replace("(", "")\
            +str(str(filePath).split(',')[1]).strip().replace("'", "").replace(")", "")
        try:
            with open(filePath, 'wb') as f:
                f.write(fileData)
        except FileNotFoundError as ex:
            pass

    def addAttachment(self):
        fid = self.tvIdentificationResult.model().sourceModel().currentFeature
        if fid is None:
            return
        settings = QSettings()
        defaultDir = settings.value('%s/last_dir' % CONFIG_NAME, '')
        files = QFileDialog.getOpenFileNames(self, self.tr('Select attachment(s)'), defaultDir)
        if not files:
            return
        files = files[0]
        to_send = { op.basename(f):readFile(f) for f in files }
        connector = self.plugin.dockwidget.getConnector()
        if fid is None:
            return
        connector.sendAttachments( fid, to_send )
        attachments = connector.get_attachments( str(fid) )
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
        attachments = connector.get_attachments( str(fid) )
        self.plugin.identifyTool.on_activities.emit( {'attachments':attachments.get('data', [])} )
    
    def addComment(self):
        fid = self.tvIdentificationResult.model().sourceModel().currentFeature
        if fid is None:
            return
        text, _ = QInputDialog.getText(self, 'DIVI QGIS Plugin', self.tr('Add new comment'))
        if not text:
            return
        connector = self.plugin.dockwidget.getConnector()
        if fid is None:
            return
        connector.addComment(fid, text)
        comments = connector.get_comments( str(fid) )
        self.plugin.identifyTool.on_activities.emit( {'comments':comments.get('data', [])} )
    
    def itemViewChanged(self, index, expanded):
        item = index.data(Qt.UserRole)
        if not isinstance(item, ActivitiesItem):
            return
        QSettings().setValue('%s/expanded/%s' % (CONFIG_NAME, item.type), expanded)
    
    def showPreviewDialog(self):
        """ Show images preview dialog """
        if self.previewDialog is None:
            #Create window if not exists
            self.previewDialog = DiviPluginPreviewDialog(self)
        model = self.tvIdentificationResult.model().sourceModel()
        item = model.findItem('attachments')
        image_items = []
        supportedFormats = QImageReader.supportedImageFormats()
        #Filter attachments by extension of supported formats
        for itm in item.childItems:
            ext = op.splitext(itm.name)[-1][1:].lower()
            if ext in supportedFormats:
                image_items.append( itm )
        fid = self.tvIdentificationResult.model().sourceModel().currentFeature
        self.previewDialog.show(fid, image_items)
    
    def showHistoryDialog(self):
        #index.parent().data(Qt.UserRole).childItems
        if self.historyDialog is None:
            #Create window if not exists
            self.historyDialog = DiviPluginHistoryDialog(self)
        model = self.tvIdentificationResult.model().sourceModel()
        item = model.findItem('history')
        self.historyDialog.show( item.childItems )
