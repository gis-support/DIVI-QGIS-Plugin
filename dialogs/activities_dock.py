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
from PyQt4.QtCore import Qt
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
        #self.btnDownloadAttachment.clicked.connect( lambda: self.itemActivated() )
    
    def itemActivated(self, index):
        item = index.data(Qt.UserRole)
        if isinstance(item, AttachmentItem):
            ext = op.splitext(item.name)[-1]
            filePath = QFileDialog.getSaveFileName(self, self.tr('Save file to...'),
                item.name, filter = '*%s' % ext)
            if not filePath:
                return
            connector = self.plugin.dockwidget.getConnector()
            fileData = connector.getFile( self.tvActivities.model().sourceModel().currentFeature, item.name )
            with open(filePath, 'wb') as f:
                f.write(fileData)
