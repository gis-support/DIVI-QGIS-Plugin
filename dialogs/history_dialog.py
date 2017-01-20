# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiviPluginHistoryDialog
                                 A QGIS plugin
 Integracja QGIS z platformą DIVI firmy GIS Support sp. z o. o.
                             -------------------
        begin                : 2017-01-20
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
from PyQt4.QtGui import QDialog
import os.path as op
from ..models.HistoryModels import HistoryModel, HistoryProxyModel, ChangeModel

FORM_CLASS, _ = uic.loadUiType(op.join(
    op.dirname(__file__), 'history_dialog.ui'))

class DiviPluginHistoryDialog(QDialog, FORM_CLASS):

    def __init__(self, plugin, parent=None):
        """Constructor."""
        super(DiviPluginHistoryDialog, self).__init__(parent)
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
        self.tblChanges.setModel( ChangeModel() )
        
        proxyChanges = HistoryProxyModel()
        proxyChanges.setSourceModel( HistoryModel() )
        self.tblHistory.setModel( proxyChanges )
        #Signals
        self.plugin.tvIdentificationResult.model().sourceModel().on_history.connect( self.historyChanged )
        self.tblHistory.selectionModel().currentChanged.connect( self.currentHistoryChanged )
        #self.tblHistory.selectionModel().currentChanged.connect( 
        #    lambda c,p: current.data(Qt.UserRole).getDetails().get('what_attributes', []) )
    
    def show(self, data=[]):
        model = self.tblHistory.model().sourceModel()
        model.addItems(data)
        super(DiviPluginHistoryDialog, self).show()
    
    def historyChanged(self):
        """ Reaload data if window is visible """
        if self.isVisible():
            self.plugin.showHistoryDialog()
    
    def currentHistoryChanged(self, current, previous):
        item = current.data(Qt.UserRole)
        if item is None:
            data = []
        else:
            data = current.data(Qt.UserRole).getDetails().get('what_attributes', [])
        self.tblChanges.model().addItems( data )
