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

from PyQt4.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal
from PyQt4.QtGui import QSortFilterProxyModel
import os.path as op
from tempfile import NamedTemporaryFile
from datetime import datetime

class HistoryModel(QAbstractTableModel):
    
    def __init__(self, parent=None):
        super(HistoryModel, self).__init__(parent)
        self.items = []
    
    def rowCount(self, parent=QModelIndex()):
        return len(self.items)
 
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
                return item.displayDate
        elif role == Qt.UserRole:
            #Return item itself
            return item
    
    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return self.tr('User')
            elif section == 1:
                return self.tr('Date')
    
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

class HistoryProxyModel(QSortFilterProxyModel):
    pass

class ChangeModel(HistoryModel):
    
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
                return item['was']
            elif index.column()==2:
                return item['is']
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
