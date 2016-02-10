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

from PyQt4.QtCore import QObject, QAbstractItemModel, Qt, QModelIndex
from PyQt4.QtGui import QIcon
from qgis.core import QgsMessageLog

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
    
    def data(self, column):
        return "" if column == 0 else None

    def parent(self):
        return self.parentItem
    
    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

class AccountItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(AccountItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')

class ProjectItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(ProjectItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')
        self.id_accounts = data.get('id_accounts')

class LayerItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(LayerItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')
        self.id_accounts = data.get('id_accounts')
        self.id_projects = data.get('id_projects')
        
        self.icon = QIcon(':/plugins/DiviPlugin/images/layer.png')

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
    
    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == 0:
            return self.tr('Dane')
        return None
    
    def addData(self, accounts, projects, layers):
        self.beginInsertRows(QModelIndex(), 0, len(accounts)-1)
        self.addAccounts(accounts)
        self.addProjects(projects)
        self.addLayers(layers)
        #QgsMessageLog.logMessage(str(accounts_map), 'DIVI')
        self.endInsertRows()
    
    def addAccounts(self, accounts):
        for account in sorted(accounts, key=lambda x:x['name']):
            item = AccountItem(account, self.rootItem )
            self.accounts_map[item.id] = item
    
    def addProjects(self, projects):
        for project in sorted(projects, key=lambda x:x['name']):
            item = ProjectItem(project, self.accounts_map[project['id_accounts']] )
            self.projects_map[item.id] = item
    
    def addLayers(self, layers):
        for layer in sorted(layers, key=lambda x:x['name']):
            item = LayerItem(layer, self.projects_map[layer['id_projects']] )
    
    def index(self, row, column, parent):
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
