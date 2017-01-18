# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiviPluginPreviewDialog
                                 A QGIS plugin
 Integracja QGIS z platformą DIVI firmy GIS Support sp. z o. o.
                             -------------------
        begin                : 2017-01-13
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

from PyQt4 import uic
from PyQt4.QtCore import QSettings, Qt
from PyQt4.QtGui import QDialog, QToolBar, QSplitter
from qgis.core import QgsApplication
from ..models.ThumbnailsModel import ThumbnailsModel
from ..widgets.ImageViewerQt import ImageViewerQt

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'preview_dialog.ui'))


class DiviPluginPreviewDialog(QDialog, FORM_CLASS):

    def __init__(self, plugin, parent=None):
        """Constructor."""
        super(DiviPluginPreviewDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.plugin = plugin
        #self.iface = plugin.iface
        
        self.setupUi(self)
        self.initGui()
    
    def initGui(self):
        self.setWindowFlags( Qt.Window )
        self.lvThumbnails.setModel( ThumbnailsModel() )
        self.fid = None
        self.viewer = ImageViewerQt()
        self.viewer.setToolTip(self.tr('Left mouse button: Pan\nRight mouse button: zoom to rectangle\nMouse wheel: Zoom In/Out'))
        self.frameLayout.addWidget(self.viewer)
        self.lvThumbnails.selectionModel().currentChanged.connect( self.showFullImage )
        #Icons
        self.btnPrevious.setIcon( QgsApplication.getThemeIcon('mActionAtlasPrev.svg') )
        self.btnNext.setIcon( QgsApplication.getThemeIcon('mActionAtlasNext.svg') )
        self.btnZoomFit.setIcon( QgsApplication.getThemeIcon('mActionZoomFullExtent.svg') )
        self.btnSave.setIcon( QgsApplication.getThemeIcon('mActionFileSave.svg') )
        #Signals
        self.btnPrevious.clicked.connect( lambda: self.changeImage(False) )
        self.btnNext.clicked.connect( lambda: self.changeImage(True) )
        self.btnZoomFit.clicked.connect( self.viewer.fitZoom )
        #self.btnZoomIn.clicked.connect( lambda: self.viewer.zoom( True ) )
        #self.btnZoomOut.clicked.connect( lambda: self.viewer.zoom( False ) )
        self.btnSave.clicked.connect( self.saveImage )
        self.btnZoomIn.setVisible( False )
        self.btnZoomOut.setVisible( False )
        self.plugin.tvIdentificationResult.model().sourceModel().on_attachments.connect( self.attachmentsChanged )
    
    def show(self, fid, images):
        """ Update images list and show window """
        self.fid = fid
        model = self.lvThumbnails.model()
        model.setImages(fid, images)
        if model.rowCount():
            self.lvThumbnails.setCurrentIndex( model.index(0,0) )
        else:
            self.viewer.setImage(None)
        super(DiviPluginPreviewDialog, self).show()
    
    def attachmentsChanged(self):
        """ Reaload data if window is visible """
        if self.isVisible():
            self.plugin.previewDialog()
    
    def showFullImage(self, index, previous=None):
        """ Show image """
        item = index.data( Qt.UserRole )
        if item is None:
            return
        self.viewer.setImage( item.getImageFull().toImage() )
    
    def changeImage(self, forward):
        """ Change image after Previous/Next button click """
        current_index = self.lvThumbnails.currentIndex()
        current_item = current_index.data( Qt.UserRole )
        model = self.lvThumbnails.model()
        if current_item is None:
            self.lvThumbnails.setCurrentIndex( model.index(0,0) )
        elif forward and model.rowCount()-1 > current_index.row():
            self.lvThumbnails.setCurrentIndex( model.index(current_index.row()+1,0) )
        elif not forward and current_index.row()>0:
            self.lvThumbnails.setCurrentIndex( model.index(current_index.row()-1,0) )
    
    def saveImage(self):
        """ Save current image to disk """
        current_index = self.lvThumbnails.currentIndex()
        current_item = current_index.data( Qt.UserRole )
        if current_item is None:
            return
        filePath = self.plugin.getSavePath( current_item.name )
        if filePath is None:
            return
        self.viewer._pixmapHandle.pixmap().save( filePath )
        
