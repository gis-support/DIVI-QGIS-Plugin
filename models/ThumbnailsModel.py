# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Activities model
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

from qgis.PyQt.QtCore import QObject, QAbstractListModel, Qt, QModelIndex, pyqtSignal, \
    QFileInfo, QSize, pyqtSignal, QBuffer, QSortFilterProxyModel
from PyQt5.QtGui import QIcon, QTextDocument, QAbstractTextDocumentLayout, QImageReader, QPixmap
from PyQt5.QtWidgets import QFileIconProvider, QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle
import os.path as op
from tempfile import NamedTemporaryFile
from datetime import datetime
from ..config import *
from ..utils.connector import DiviConnector

ICONS_CACHE = {}

class TreeItem(QObject):
    '''
    a python object used to return row/column data, and keep note of
    it's parents and/or children
    '''
    def __init__(self, item, parentItem):
        super(TreeItem, self).__init__(parentItem)
        self.childItems = []
        
        if parentItem:
            parentItem.appendChild(self)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 1
    
    def data(self, column):
        return "" if column == 0 else None
    
    def row(self):
        return 0
    
    def appendChild(self, item):
        self.childItems.append(item)
        self.connect(item, SIGNAL("itemRemoved"), self.childRemoved)
    
    def childRemoved(self, child):
        self.itemChanged()
    
    def itemChanged(self):
        self.emit( SIGNAL("itemChanged"), self )
    
    def itemRemoved(self):
        self.emit(SIGNAL("itemRemoved"), self)
    
    def removeChild(self, row):
        if row >= 0 and row < len(self.childItems):
            self.disconnect(self.childItems[row], SIGNAL("itemRemoved"), self.childRemoved)
            del self.childItems[row]
    
    def removeChilds(self):
        for i in reversed(range(self.childCount())):
            self.removeChild(i)

class ImageItem(TreeItem):
    
    def __init__(self, fid, image, parent=None):
        super(ImageItem, self).__init__(self, parent)
        self.name = image.name
        self.fid = fid
        self.icon = None
        self.image = None
        self.getImageThumbnail()
    
    def getImageThumbnail(self):
        pixmap = self.getImage()
        #pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio)
        self.icon = QIcon( pixmap )
    
    def getImageFull(self):
        if self.image is None:
            pixmap = self.getImage(False)
            self.image = pixmap
        return self.image
    
    def getImage(self, as_thumbnail=True):
        connector = DiviConnector()
        img = connector.getFile(self.fid, self.name, as_thumbnail=as_thumbnail)
        del connector
        b = QBuffer( img )
        im = QImageReader( b )
        return QPixmap.fromImageReader( im )

class ThumbnailsModel(QAbstractListModel):
    
    def __init__(self, layerType='vector', parent=None):
        super(ThumbnailsModel, self).__init__(parent)
        self.images = []
    
    def data(self, index, role):
        if not index.isValid():
            return None
        item = self.images[index.row()]
        if role == Qt.DisplayRole:
            return item.name
        elif role == Qt.DecorationRole and hasattr(item, 'icon'):
            return item.icon
        elif role == Qt.ToolTipRole:
            return item.name
        elif role == Qt.UserRole:
            #Return item itself
            return item
    
    def rowCount(self, parent=QModelIndex()):
        return len(self.images)
    
    def removeAll(self, parent=QModelIndex()):
        self.beginRemoveRows(parent, 0, self.rowCount()-1)
        self.images = []
        self.endRemoveRows()
    
    def setImages(self, fid, images):
        self.removeAll()
        self.beginInsertRows(QModelIndex(), 0, len(images)-1)
        for image in images:
            self.images.append( ImageItem(fid, image) )
        self.endInsertRows()
