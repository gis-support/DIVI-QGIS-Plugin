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

from qgis.PyQt.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal, QSize, QSortFilterProxyModel
from PyQt5.QtGui import QBrush, QColor
import os.path as op
from tempfile import NamedTemporaryFile
from datetime import datetime

class BaseModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super(BaseModel, self).__init__(parent)
        self.items = []
    
    def rowCount(self, parent=QModelIndex()):
        return len(self.items)
    
    def insertRows(self, position, rows, parent=QModelIndex()):
        self.beginInsertRows(parent, position, position + len(rows) - 1)
        for i, item in enumerate(rows):
            self.items.insert(position+i, item)
        self.endInsertRows()
        return True
    
    def removeRows(self, row=0, count=None, parent=QModelIndex()):
        if count is None:
            count = self.rowCount()
        self.beginRemoveRows(parent, row, count+row-1)
        self.items = []
        self.endRemoveRows()
        return True
    
    def addItems(self, data, parent=QModelIndex()):
        self.removeRows()
        if data:
            self.insertRows(0, data)
    
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

class HistoryModel(BaseModel):
 
    def columnCount(self, parent=QModelIndex()):
        return 2
    
    def data(self, index, role):
        if not index.isValid():
            return None
        item = self.items[index.row()]
        if role == Qt.DisplayRole:
            if index.column()==0:
                return item.user
            elif index.column()==1:
                '''
                if 'geom' in item.description:
                    return 'X'
            elif index.column()==2:
                if 'atr' in item.description:
                    return 'X'
            elif index.column()==3:'''
                return item.displayDate
            '''elif role == Qt.SizeHintRole:
            if index.column() in (1, 2):
                return QSize(100, 10)'''
        elif role == Qt.UserRole:
            #Return item itself
            return item
    
    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return self.tr('User')
            elif section == 1:
                '''
                return self.tr('Geom')
            elif section == 2:
                return self.tr('Attrs')
            elif section == 3:'''
                return self.tr('Date')

class HistoryProxyModel(QSortFilterProxyModel):
    pass

class ChangeModel(BaseModel):
    
    def columnCount(self, parent=QModelIndex()):
        return 3
    
    def data(self, index, role):
        if not index.isValid():
            return None
        item = self.items[index.row()]
        if role == Qt.DisplayRole:
            if index.column()==0:
                return item['key']
            elif index.column()==1:
                if item['was'] is None:
                    return 'NULL'
                else:
                    return item['was']
            elif index.column()==2:
                if item['is'] is None:
                    return 'NULL'
                else:
                    return item['is']
        elif role == Qt.ForegroundRole:
            if (index.column() == 1 and item['was'] is None) or (index.column() == 2 and item['is'] is None):
                return QBrush(QColor('gray'))
        elif role == Qt.UserRole:
            #Return item itself
            return item
    
    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return self.tr('Field')
            elif section == 1:
                return self.tr('Was')
            elif section == 2:
                return self.tr('Is')
