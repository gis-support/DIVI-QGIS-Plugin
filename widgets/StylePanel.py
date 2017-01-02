# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Style panel
                                 A QGIS plugin
 Integracja QGIS z platformą DIVI firmy GIS Support sp. z o. o.
                             -------------------
        begin                : 2017-01-02
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

from qgis.core import QgsMapLayer, QgsApplication
from qgis.gui import QgsMapLayerConfigWidget, QgsMapLayerConfigWidgetFactory,\
    QgsFieldProxyModel
from PyQt4.QtGui import QVBoxLayout, QIcon
from PyQt4 import uic
import os.path as op

panelWidget = uic.loadUi(op.join( op.dirname(__file__), 'StylePanel.ui') )

class DiviStylePanel(QgsMapLayerConfigWidget):
    
    panelWidget = panelWidget
    
    def __init__(self, layer, canvas, parent):
        super(DiviStylePanel, self).__init__(layer, canvas, parent)
        self.layer = layer
        
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins( 0, 0, 0, 0 )
        self.layout().addWidget( self.panelWidget )
        
        #Unique
        self.panelWidget.cmbUniqueAttr.setLayer( layer )
        #Gradual
        self.panelWidget.cmbGradualAttr.setLayer( layer )
        self.panelWidget.cmbGradualAttr.setFilters( QgsFieldProxyModel.Numeric )
 
    def apply(self):
        pass

class DiviStylePanelFactory(QgsMapLayerConfigWidgetFactory):
    def icon(self):
        return QIcon(':/plugins/DiviPlugin/images/icon.png')
 
    def title(self):
        return 'DIVI styles'
 
    def supportsLayer( self, layer):
        return (layer.type() == QgsMapLayer.VectorLayer) and (layer.customProperty('DiviId') is not None)

    def createWidget(self, layer, canvas, dockWidget, parent):
        return DiviStylePanel(layer, canvas, parent)
    
    def supportsStyleDock(self):
        return True
