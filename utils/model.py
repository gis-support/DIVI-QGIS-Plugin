# -*- coding: utf-8 -*-
"""
/***************************************************************************
 model
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

from PyQt4.QtCore import QObject, QAbstractItemModel, Qt, QModelIndex, SIGNAL
from PyQt4.QtGui import QIcon, QFont, QSortFilterProxyModel
from qgis.core import QgsMessageLog
import locale

class TreeItem(QObject):
    '''
    a python object used to return row/column data, and keep note of
    it's parents and/or children
    '''
    def __init__(self, item, parentItem):
        super(TreeItem, self).__init__()
        self.itemData = item
        self.parentItem = parentItem
        self.childItems = []
        
        if parentItem:
            parentItem.appendChild(self)

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 1
    
    def childRemoved(self, child):
        self.itemChanged()

    def itemChanged(self):
        self.emit( SIGNAL("itemChanged"), self )
    
    def data(self, column):
        return "" if column == 0 else None

    def parent(self):
        return self.parentItem
    
    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0
    
    def removeChild(self, row):
        if row >= 0 and row < len(self.childItems):
            self.childItems[row].itemData.deleteLater()
            self.disconnect(self.childItems[row], SIGNAL("itemRemoved"), self.childRemoved)
            del self.childItems[row]

class LoadingItem(TreeItem):
    
    def __init__(self, parent=None):
        super(LoadingItem, self).__init__(self, parent)
        self.name = self.trUtf8(u'Pobieranie danych...')
        
        self.icon = QIcon(':/plugins/DiviPlugin/images/downloading.png')

class AccountItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(AccountItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')
        self.abstract = data.get('description')

class ProjectItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(ProjectItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')
        self.id_accounts = data.get('id_accounts')
        self.abstract = data.get('description')

class LayerItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(LayerItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')
        self.id_accounts = data.get('id_accounts')
        self.id_projects = data.get('id_projects')
        self.abstract = data.get('abstract')
        self.fields = data.get('fields')
        
        self.icon = QIcon(':/plugins/DiviPlugin/images/layer.png')
        self.items = []
        self.fields_mapper = {}
        self.transaction = None
    
    def updateData(self, data):
        for key in ['fields', 'name', 'abstract']:
            if key in data:
                setattr(self, key, data[key])

class TableItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(TableItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')
        self.id_accounts = data.get('id_accounts')
        self.id_projects = data.get('id_projects')
        self.abstract = data.get('abstract')
        self.fields = data.get('fields')
        
        self.icon = QIcon(':/plugins/DiviPlugin/images/table.png')
        self.items = []
        self.transaction = None

class DiviModel(QAbstractItemModel):
    
    def __init__(self, parent=None):
        super(DiviModel, self).__init__(parent)
        
        self.accounts_map = {}
        self.projects_map = {}
        
        self.rootItem = TreeItem(None, None)
    
    def columnCount(self, parent):
        return 1
    
    def data(self, index, role):
        if not index.isValid():
            return None
        
        item = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.name
        elif role == Qt.DecorationRole and hasattr(item, 'icon'):
            return item.icon
        elif role == Qt.FontRole and hasattr(item, 'items'):
            font = QFont()
            font.setBold(bool(item.items))
            return font
        elif role == Qt.ToolTipRole:
            return item.abstract
        elif role == Qt.UserRole:
            #Return item itself
            return item
        elif role == Qt.UserRole+1:
            #Required for finding item
            if isinstance(item,LayerItem):
                return 'layer@%s' % item.id
            elif isinstance(item,TableItem):
                return 'table@%s' % item.id
            elif isinstance(item,ProjectItem):
                return 'project@%s' % item.id
            elif isinstance(item,AccountItem):
                return 'account@%s' % item.id
        elif role == Qt.UserRole+2:
            return item.metaObject().className()
    
    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == 0:
            return self.tr('Dane')
        return None
    
    def showLoading(self):
        self.removeAll()
        self.beginInsertRows(QModelIndex(), 0, 1)
        item = LoadingItem( self.rootItem )
        self.endInsertRows()
    
    def addData(self, accounts, projects, layers, tables):
        self.removeAll()
        self.beginInsertRows(QModelIndex(), 0, len(accounts)-1)
        self.addAccounts(accounts)
        self.addProjects(projects)
        self.addLayers(layers)
        self.addTables(tables)
        self.endInsertRows()
    
    def addAccounts(self, accounts):
        for account in accounts:
            item = AccountItem(account, self.rootItem )
            self.accounts_map[item.id] = item
    
    def addProjects(self, projects):
        for project in projects:
            item = ProjectItem(project, self.accounts_map[project['id_accounts']] )
            self.projects_map[item.id] = item
    
    def addLayers(self, layers):
        for layer in layers:
            item = LayerItem(layer, self.projects_map[layer['id_projects']] )
    
    def addTables(self, tables):
        for table in tables:
            item = TableItem(table, self.projects_map[table['id_projects']] )
    
    def addProjectLayers(self, project, layers):
        parent = self.findItem(project.id, 'project', True)
        count = len(project.childItems)
        self.beginInsertRows(parent, count, count+len(layers)-1)
        self.addLayers(layers)
        self.endInsertRows()
    
    def removeAll(self):
        rows_count = self.rootItem.childCount()
        if not rows_count:
            return
        for row in reversed(range(rows_count)):
            #Remove child items
            index = self.index(row,0)
            item = index.internalPointer()
            self.removeRows(0,item.childCount(),index)
            #Remove root element (account)
            item.itemData.deleteLater()
            del self.rootItem.childItems[row]
    
    def removeRows(self, row, count, parent):
        self.beginRemoveRows(parent, row, count+row-1)
        item = parent.internalPointer()
        for i in range(row, count+row):
            item.removeChild(row)
        self.endRemoveRows()
    
    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parentItem = parent.internalPointer() if parent.isValid() else self.rootItem
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        return QModelIndex()
    
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        parentItem = parent.internalPointer() if parent.isValid() else self.rootItem
        return parentItem.childCount()

    def hasChildren(self, parent):
        parentItem = parent.internalPointer() if parent.isValid() else self.rootItem
        return parentItem.childCount() > 0
    
    def findItem(self, oid, item_type='layer', as_model=False):
        if oid is None:
            return
        indexes = self.match(
            self.index(0,0),
            Qt.UserRole+1,
            '%s@%s' % (item_type, oid),
            1,
            Qt.MatchRecursive
        )
        if indexes:
            if as_model:
                return indexes[0]
            else:
                return indexes[0].data(role=Qt.UserRole)

class DiviProxyModel(QSortFilterProxyModel):
    # Source: http://gaganpreet.in/blog/2013/07/04/qtreeview-and-custom-filter-models/
    ''' Class to override the following behaviour:
            If a parent item doesn't match the filter,
            none of its children will be shown.
 
        This Model matches items which are descendants
        or ascendants of matching items.
    '''
 
    def filterAcceptsRow(self, row_num, source_parent):
        ''' Overriding the parent function '''
 
        # Check if the current row matches
        if self.filter_accepts_row_itself(row_num, source_parent):
            return True
 
        # Traverse up all the way to root and check if any of them match
        if self.filter_accepts_any_parent(source_parent):
            return True
 
        # Finally, check if any of the children match
        return self.has_accepted_children(row_num, source_parent)
 
    def filter_accepts_row_itself(self, row_num, parent):
        return super(DiviProxyModel, self).filterAcceptsRow(row_num, parent)
 
    def filter_accepts_any_parent(self, parent):
        ''' Traverse to the root node and check if any of the
            ancestors match the filter
        '''
        while parent.isValid():
            if self.filter_accepts_row_itself(parent.row(), parent.parent()):
                return True
            parent = parent.parent()
        return False
 
    def has_accepted_children(self, row_num, parent):
        ''' Starting from the current node as root, traverse all
            the descendants and test if any of the children match
        '''
        model = self.sourceModel()
        source_index = model.index(row_num, 0, parent)
 
        children_count =  model.rowCount(source_index)
        for i in xrange(children_count):
            if self.filterAcceptsRow(i, source_index):
                return True
        return False
    
    def lessThan(self, left, right):
        lvalue = left.data()
        rvalue = right.data()
        if lvalue is None:
            return True
        if rvalue is None:
            return False
        return locale.strcoll(lvalue.lower(), rvalue.lower()) > 0

