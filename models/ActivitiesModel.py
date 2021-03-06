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

from qgis.PyQt.QtCore import QObject, QSortFilterProxyModel, QAbstractItemModel, Qt, QModelIndex, pyqtSignal, \
    QFileInfo, QSize, QSettings, QVariant, QObject
from PyQt5.QtGui import QIcon, QTextDocument, QAbstractTextDocumentLayout
from PyQt5.QtWidgets import QStyledItemDelegate, QFileIconProvider, QStyleOptionViewItem, QApplication, QStyle
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
    itemRemoved = pyqtSignal(object)
    itemChanged = pyqtSignal(object)
    
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
        item.itemRemoved.connect(self.childRemoved)
    
    def childRemoved(self, child):
        self.itemChanged.emit(child)
    
    #def itemChanged(self):
     #   self.emit( SIGNAL("itemChanged"), self )
    
    #def itemRemoved(self):
    #    self.emit(SIGNAL("itemRemoved"), self)
    
    def removeChild(self, row):
        if row >= 0 and row < len(self.childItems):
            self.childItems[row].itemRemoved.disconnect(self.childRemoved)
            del self.childItems[row]
    
    def removeChilds(self):
        for i in reversed(range(self.childCount())):
            self.removeChild(i)

class ActivitiesItem(TreeItem):
    
    def __init__(self, _type, parent):
        super(ActivitiesItem, self).__init__(self, parent)
        self.type = _type
        if _type == 'attachments':
            self.name = self.tr('Attachments')
        elif _type == 'comments':
            self.name = self.tr('Comments')
        elif _type == 'history':
            self.name = self.tr('History')
        elif _type == 'raster':
            self.name = self.tr('Raster')
        self.icon = QIcon(':/plugins/DiviPlugin/images/%s.png' % self.type)
    
    def identifier(self):
        return self.type
    
    def text(self):
        #Don't count LoadingItem
        childCount = len([ child for child in self.childItems if not type(child) is LoadingItem ])
        return '%s [%d]' % (self.name, childCount )

class BaseActivityItem(TreeItem):
    
    def identifier(self):
        return self.name
    
    def text(self):
        return self.name

class LoadingItem(BaseActivityItem):
    
    def __init__(self, data,parent):
        super(LoadingItem, self).__init__(self, parent)
        self.name = self.tr(u'Downloading data...')
        self.icon = QIcon(':/plugins/DiviPlugin/images/downloading.png')

class AttachmentItem(BaseActivityItem):
    
    def __init__(self, attachment, parent):
        super(AttachmentItem, self).__init__(self, parent)
        self.name = attachment['url']
        self.getIcon()
        self.tooltip = self.tr('<b>Added by:</b> {email}<br/><b>Time:</b> {posted_at}').format( **attachment )
    
    def getIcon(self):
        ext = op.splitext(self.name)[-1]
        if ext not in ICONS_CACHE:
            with NamedTemporaryFile(suffix=ext) as f:
                ICONS_CACHE[ext] = QFileIconProvider().icon(QFileInfo(f.name))
        self.icon = ICONS_CACHE[ext]

class CommentItem(BaseActivityItem):
    
    icon = QIcon(':/plugins/DiviPlugin/images/user.png')
    
    def __init__(self, comment, parent):
        super(CommentItem, self).__init__(self, parent)
        self.comment = '<br/>'.join(comment['content'].splitlines())
        self.user = comment['id_users']
        self.date = datetime.utcfromtimestamp( comment['posted_at'] )
        self.displayDate = self.date.replace(microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    
    @property
    def tooltip(self):
        return self.comment
    
    @property
    def name(self):
        return u'<b>{}</b><br/><i>{}</i><br/>{}'.format( self.user, self.displayDate, self.comment )

class ChangeItem(BaseActivityItem):
    
    icon = QIcon(':/plugins/DiviPlugin/images/history.png')
    
    def __init__(self, change, parent):
        super(ChangeItem, self).__init__(self, parent)
        self.id = change['id']
        self.description = change['what']
        self.user = change['email']
        self.date = datetime.strptime( change['when'], "%Y-%m-%d %H:%M:%S.%f" )
        self.displayDate = self.date.replace(microsecond=0).strftime('%d.%m.%Y %H:%M:%S')
        self.details = None
    
    @property
    def tooltip(self):
        return self.description
    
    @property
    def name(self):
        return u'<b>{}</b><br/><i>{}</i><br/>{}'.format( self.user, self.displayDate, self.description )
    
    def getDetails(self):
        if self.details is None:
            connector = DiviConnector()
            self.details = connector.getChange(self.id)
            del connector
        return self.details

class RasterItem(BaseActivityItem):
    
    def __init__(self, result, parent):
        super(RasterItem, self).__init__(self, parent)
        row, value = result
        self.value = value
        self.name = self.tr('Band %d: %s') % (row, self.value)

class ActivitiesModel(QAbstractItemModel):
    
    expand = pyqtSignal(QModelIndex)
    layerTypeChanged = pyqtSignal(str)
    on_attachments = pyqtSignal()
    on_history = pyqtSignal()
    
    def __init__(self, layerType='vector', parent=None):
        super(ActivitiesModel, self).__init__(parent)
        
        self.rootItem = TreeItem(None, None)
        self.layerType = None
        self.setLayerType(layerType)
        
        self.setCurrentFeature(None)
    
    def columnCount(self, parent):
        return 1
    
    def data(self, index, role):
        if not index.isValid():
            return None
        item = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.text()
        elif role == Qt.DecorationRole and hasattr(item, 'icon'):
            return item.icon
        elif role == Qt.ToolTipRole and hasattr(item, 'tooltip'):
            return item.tooltip
        elif role == Qt.UserRole:
            #Return item itself
            return item
        elif role == Qt.UserRole+1:
            #Return item itself
            return item.identifier()
    
    def rowCount(self, parent):
        parentItem = parent.data(Qt.UserRole) if parent.isValid() else self.rootItem
        return parentItem.childCount()
    
    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parentItem = parent.data(Qt.UserRole) if parent.isValid() else self.rootItem
        childItem = parentItem.child(row)
        if childItem:
            a = self.createIndex(row, column, childItem)
            return a
        return QModelIndex()
    
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.data(Qt.UserRole)
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)
    
    def removeRows(self, row, count, parent):
        if not parent.isValid():
            item = self.rootItem
        else:
            item = parent.data(Qt.UserRole)
        self.beginRemoveRows(parent, row, count+row-1)
        item.removeChilds()
        self.endRemoveRows()
    
    def removeAll(self, parent=None):
        if parent is None:
            item = self.index(0,0).data(Qt.UserRole)
            self.removeRows(0, self.rootItem.childCount(), self.index(0,0).parent())
            return
        item = parent.data(Qt.UserRole)
        self.removeRows(0, item.childCount(), parent)
    
    def addActivities(self, data):
        #Add attachments
        self.setLayerType('vector')
        if 'attachments' in data:
            attachments = data['attachments']
            attachment_index = self.findItem('attachments', as_model=True)
            if attachment_index is not None:
                self.addItems(attachment_index, attachments, AttachmentItem)
            self.on_attachments.emit()
        #Add comments
        if 'comments' in data:
            comments = data['comments']
            comment_index = self.findItem('comments', as_model=True)
            if comment_index is not None:
                self.addItems(comment_index, comments, CommentItem)
        #Add history
        if 'changes' in data:
            changes = data['changes']
            history_index = self.findItem('history', as_model=True)
            if history_index is not None:
                self.addItems(history_index, changes, ChangeItem)
            self.on_history.emit()
    
    def addItems(self, parent, data, model):
        parent_item = parent.data(Qt.UserRole)
        self.removeAll(parent)
        if data:
            self.beginInsertRows(parent, 0, len(data)-1)
            for item in data:
                model( item, parent_item )
            self.endInsertRows()
    
    def setLoading(self):
        attachment_index = self.findItem('attachments', as_model=True)
        if attachment_index is not None:
            self.addItems(attachment_index, [None], LoadingItem)
        comment_index = self.findItem('comments', as_model=True)
        if comment_index is not None:
            self.addItems(comment_index, [None], LoadingItem)
        history_index = self.findItem('history', as_model=True)
        if history_index is not None:
            self.addItems(history_index, [None], LoadingItem)
    
    def findItem(self, identifier, as_model=False):
        if identifier is None:
            return
        indexes = self.match(
            self.index(0,0),
            Qt.UserRole+1,
            identifier,
            1,
            Qt.MatchRecursive
        )
        if indexes:
            if as_model:
                return indexes[0]
            else:
                return indexes[0].data(role=Qt.UserRole)
    
    def setCurrentFeature(self, feature):
        self.currentFeature = feature
    
    def setLayerType(self, layerType):
        if self.layerType == layerType:
            self.setExpand()
            return
        self.removeAll()
        self.layerType = layerType
        self.layerTypeChanged.emit( self.layerType )
        if layerType=='vector':
            self.beginInsertRows(self.index(0,0), 0, 2)
            ActivitiesItem('attachments', self.rootItem)
            ActivitiesItem('comments', self.rootItem)
            ActivitiesItem('history', self.rootItem)
            self.endInsertRows()
        else:
            self.beginInsertRows(self.index(0,0), 0, 0)
            ActivitiesItem('raster', self.rootItem)
            self.endInsertRows()
        self.setExpand()
    
    def clearItems( self ):
        #Clear identification tree
        self.removeAll()
        if self.layerType=='vector':
            self.beginInsertRows(self.index(0,0), 0, 2)
            ActivitiesItem('attachments', self.rootItem)
            ActivitiesItem('comments', self.rootItem)
            ActivitiesItem('history', self.rootItem)
            self.endInsertRows()
        else:
            self.beginInsertRows(self.index(0,0), 0, 0)
            ActivitiesItem('raster', self.rootItem)
            self.endInsertRows()
        self.setExpand()
    
    def setExpand(self):
        def expand( itemTypes ):
            for itemType in itemTypes:
                if settings.value('%s/expanded/%s' % (CONFIG_NAME, itemType), False, bool):
                    self.expand.emit( self.findItem(itemType, True) )
        
        settings = QSettings()
        if self.layerType=='vector':
            expand(['attachments', 'comments', 'history'])
        else:
            expand(['raster'])
    
    def addRasterResult(self, data):
        self.setLayerType('raster')
        index = self.findItem('raster', as_model=True)
        if index is not None:
            self.addItems(index, list(enumerate(data, start=1)), RasterItem)
        

class ActivitiesProxyModel(QSortFilterProxyModel):
    
    def lessThan(self, left, right):
        left_item = left.data(Qt.UserRole)
        if isinstance( left.data(Qt.UserRole), ActivitiesItem ):
            #Order: attachments -> comments -> history
            if left_item.type == 'attachments':
                return False
            if left_item.type == 'comments':
                return False
        return True

class HTMLDelegate(QStyledItemDelegate):
    """ http://stackoverflow.com/a/5443112 """
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        item = index.data(Qt.UserRole)
        if isinstance(item, (CommentItem, ChangeItem)):
            options.decorationAlignment = Qt.AlignHCenter
        self.initStyleOption(options,index)

        if options.widget is None:
            style = QApplication.style()
        else:
            style = options.widget.style()
        
        doc = QTextDocument()
        doc.setHtml(options.text)
        
        options.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()

        # Highlighting text if item is selected
        #if (optionV4.state & QStyle::State_Selected)
            #ctx.palette.setColor(QPalette::Text, optionV4.palette.color(QPalette::Active, QPalette::HighlightedText))

        textRect = style.subElementRect(QStyle.SE_ItemViewItemText, options)
        painter.save()
        painter.translate(textRect.topLeft())
        painter.setClipRect(textRect.translated(-textRect.topLeft()))
        doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options,index)

        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width())
        return QSize(doc.idealWidth(), doc.size().height())
