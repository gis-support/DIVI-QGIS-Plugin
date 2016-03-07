# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiviPluginImportDialog
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

import os
from functools import partial

from PyQt4 import QtGui, uic
from PyQt4.QtCore import pyqtSignal, QSettings, Qt, QRegExp
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsVectorLayer, QGis,\
    QgsApplication
from qgis.gui import QgsMessageBar
from ..utils.connector import DiviConnector
from ..utils.model import DiviModel, LeafFilterProxyModel, LayerItem, TableItem, \
    ProjectItem
from ..utils.widgets import ProgressMessageBar
from ..utils.model import AccountItem

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'import_dialog.ui'))


class DiviPluginImportDialog(QtGui.QDialog, FORM_CLASS):

    def __init__(self, plugin, parent=None):
        """Constructor."""
        super(DiviPluginImportDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.plugin = plugin
        self.iface = plugin.iface
        
        self.setupUi(self)
        
        self.cmbLayers.currentIndexChanged[str].connect(self.eLayerName.setText)
        
        self.loadLayers()
        self.loadAccounts()
        self.loadProjects(self.cmbAccounts.currentIndex())
        
        self.cmbAccounts.currentIndexChanged[int].connect(self.loadProjects)
    
    def loadLayers(self):
        self.cmbLayers.clear()
        for _, layer in QgsMapLayerRegistry.instance().mapLayers().iteritems():
            self.cmbLayers.addItem(layer.name(), layer)
    
    def loadAccounts(self):
        self.cmbAccounts.clear()
        for account in self.getModelType("Account"):
            self.cmbAccounts.addItem(account.name, account.id)
    
    def loadProjects(self, account):
        accountid = self.cmbAccounts.itemData(account)
        self.cmbProjects.clear()
        QgsMessageLog.logMessage(str(accountid), 'DIVI')
        for project in self.getModelType("Project", accountid):
            self.cmbProjects.addItem(project.name, project.id)
    
    def getModelType(self, modelType, parentid=None):
        model = self.plugin.dockwidget.tvData.model().sourceModel()
        if parentid is None:
            parent = model.index(0,0)
        else:
            parent = self.plugin.dockwidget.findLayerItem(parentid, 'account', True)
        indexes = model.match(
            parent,
            Qt.UserRole+2,
            modelType,
            -1,
            Qt.MatchRecursive | Qt.MatchStartsWith
        )
        for index in indexes:
            yield index.data(role=Qt.UserRole)
