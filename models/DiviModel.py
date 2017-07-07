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
from PyQt4.QtGui import QIcon, QFont, QSortFilterProxyModel, QColor
from qgis.core import QgsMessageLog, QgsDataSourceURI, QgsPalLayerSettings, QGis,\
    QgsLineSymbolV2, QgsFillSymbolV2, QgsMarkerSymbolV2, QgsRendererRangeV2,\
    QgsGraduatedSymbolRendererV2, QgsRendererCategoryV2, QgsCategorizedSymbolRendererV2,\
    QgsSvgMarkerSymbolLayerV2
from ..utils.connector import DiviConnector
from ..config import *
import locale
from tempfile import gettempdir
from os import path as op, mkdir
import base64
import urllib

class TreeItem(QObject):
    '''
    a python object used to return row/column data, and keep note of
    it's parents and/or children
    '''
    def __init__(self, item, parentItem):
        super(TreeItem, self).__init__(parentItem)
        self.itemData = item
        self.childItems = []
        
        if parentItem:
            parentItem.appendChild(self)

    def appendChild(self, item):
        self.childItems.append(item)
        self.connect(item, SIGNAL("itemRemoved"), self.childRemoved)

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
    
    def itemRemoved(self):
        self.emit(SIGNAL("itemRemoved"), self)
    
    def data(self, column):
        return "" if column == 0 else None
    
    def row(self):
        if self.parent():
            return self.parent().childItems.index(self)
        return 0
    
    def removeChild(self, row):
        if row >= 0 and row < len(self.childItems):
            self.childItems[row].itemData.deleteLater()
            self.disconnect(self.childItems[row], SIGNAL("itemRemoved"), self.childRemoved)
            del self.childItems[row]
    
    def removeChilds(self):
        for i in reversed(range(self.childCount())):
            self.removeChild(i)

class LoadingItem(TreeItem):
    
    def __init__(self, parent=None):
        super(LoadingItem, self).__init__(self, parent)
        self.name = self.tr(u'Downloading data...')
        
        self.icon = QIcon(':/plugins/DiviPlugin/images/downloading.png')

class ProjectItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(ProjectItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')
        self.abstract = data.get('description')
    
    def identifier(self):
        return 'project@%s' % self.id
    
    def loadedChilds(self):
        """ True if any layer/table from this project is loaded """
        return any( bool(child.items) for child in self.childItems )

class LayerItem(TreeItem):
    
    def __init__(self, data, parent=None):
        super(LayerItem, self).__init__(self, parent)
        self.name = data.get('name')
        self.id = data.get('id')
        self.id_projects = data.get('id_projects')
        self.abstract = data.get('abstract')
        self.data_type = data.get('data_type')
        self.items = []
    
    def updateData(self, data):
        for key in ['fields', 'name', 'abstract']:
            if key in data:
                setattr(self, key, data[key])

class TableItem(LayerItem):
    
    def __init__(self, data, parent=None):
        super(TableItem, self).__init__(data, parent)
        self.fields = data.get('fields')
        self.fields_mapper = {}
        self.icon = QIcon(':/plugins/DiviPlugin/images/table.png')
        self.transaction = None
    
    def identifier(self):
        return 'table@%s' % self.id

class VectorItem(TableItem):
    
    def __init__(self, data, parent=None):
        super(VectorItem, self).__init__(data, parent)
        self.icon = QIcon(':/plugins/DiviPlugin/images/vector.png')
        self.style = data.get('visual', {})
    
    def identifier(self):
        return 'vector@%s' % self.id
    
    def setQgisStyle(self, layer):
        """ Set layer style based on DIVI style """
        if not self.style:
            return
        styleType = self.style.get('type', 'single')
        #Get symbol class based on layer geoemtry type
        if layer.geometryType()==QGis.Point:
            symbolClass = QgsMarkerSymbolV2
        elif layer.geometryType()==QGis.Line:
            symbolClass =  QgsLineSymbolV2
        else:
            symbolClass =  QgsFillSymbolV2
        #Set style
        if styleType=='single':
            #Single symbol
            externalGraphic = self.style.get('externalGraphic')
            if externalGraphic:
                symbol = self.createSvgSymbol( self.style )
                layer.rendererV2().symbols()[0].changeSymbolLayer(0, symbol)
            else:
                symbol = self.createSymbol( symbolClass, self.style )
                layer.rendererV2().setSymbol( symbol )
        else:
            rules = []
            attribute = self.style['attribute']['key']
            if styleType=='classified':
                #Graduated symbol
                for rule in self.style['rules']:
                    if 'val' in rule['filter']:
                        #Min value is taken from attributes
                        minVal = layer.minimumValue( layer.fields().fieldNameIndex(attribute) )
                        maxVal = rule['filter']['val']
                    else:
                        minVal = rule['filter']['lo']
                        maxVal = rule['filter']['hi']
                    symbol = self.createSymbol( symbolClass, rule['symbol'] )
                    externalGraphic = rule['symbol'].get('externalGraphic')
                    if externalGraphic:
                        #Set SVG graphic as symbol
                        symbolSvg = self.createSvgSymbol( rule['symbol'] )
                        symbol.changeSymbolLayer(0, symbolSvg)
                    rules.append( QgsRendererRangeV2( float(minVal), float(maxVal), symbol, '{} - {}'.format(minVal, maxVal)) )
                renderer = QgsGraduatedSymbolRendererV2(attribute, rules)
            elif styleType=='unique':
                #Unique values symbol
                attrType = self.style['attribute']['type']
                for category in self.style['rules']:
                    symbol = self.createSymbol( symbolClass, category['symbol'] )
                    externalGraphic = category['symbol'].get('externalGraphic')
                    if externalGraphic:
                        symbolSvg = self.createSvgSymbol( category['symbol'] )
                        symbol.changeSymbolLayer(0, symbolSvg)
                    value = category['filter']['val']
                    rules.append( QgsRendererCategoryV2(self.parseValueType(value, attrType), symbol, value) )
                renderer = QgsCategorizedSymbolRendererV2(attribute, rules)
            layer.setRendererV2(renderer)
        #Set layer transparency
        layer.setLayerTransparency( self.parseTransparency( self.style.get('fillOpacity', 0.7) ) ) #Layer transparency
        #Labeling
        if self.style.get('label') is not None:
            palyr = QgsPalLayerSettings()
            palyr.readFromLayer( layer )
            palyr.enabled = True
            palyr.fieldName = self.style['label']['key']
            palyr.bufferDraw = True
            palyr.bufferSize = int(self.style.get('labelOutlineWidth', 1))
            palyr.textFont.setPointSize( int(self.style.get('labelFontSize', 12)) )
            palyr.textColor = self.hex2QColor( self.style.get('labelFontColor', '#000000') )
            palyr.writeToLayer( layer )
        layer.triggerRepaint()
    
    def createSymbol( self, symbolClass, data ):
        """ Create QGIS symblo from DIVI style definition """
        return symbolClass.createSimple({
                'color': self.hex2str( data.get('fillColor', '#abcdea') ), #Fill color
                'outline_color': self.hex2str( data.get('strokeColor', '#aeabea') ), #Outline color
                'outline_width': str( float(data.get('strokeWidth', 3))/10), #Outline width
                'size' : str( float(data.get('pointRadius', 6))/5 ) #Point size
            })
    
    def createSvgSymbol( self, data ):
        """ Create SVG  """
        return QgsSvgMarkerSymbolLayerV2.create( {
                'name' : self.getIcon(data['externalGraphic']),
                'color': self.hex2str( data.get('fillColor', '#abcdea') ), #Fill color
                'outline_color': self.hex2str( data.get('strokeColor', '#aeabea') ), #Outline color
                'outline_width': str( float(data.get('strokeWidth', 3))/10), #Outline width
                'size' : str( float(data.get('pointRadius', 6))/2 ) #Point size
            })
    
    def getIcon(self, name):
        """ External graphic based on Nathan Woodrow article:
        https://nathanw.net/2016/02/04/live-svgs/
        """
        path = op.join(gettempdir(), 'divi')
        if not op.exists( path ):
            mkdir( path )
        
        svg = """
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg>
  <g>
    <image xlink:href="data:image/jpeg;base64,{0}" height="256" width="320" />
  </g>
</svg>
"""
        data = urllib.urlopen( '%s/icons/%s' % (DIVI_HOST, name) )
        svgFile = '%s.svg' % name.replace('/', '_')
        svgPath = op.join(path, svgFile)
        b64response = base64.b64encode(data.read())
        newsvg = svg.format(b64response).replace('\n','')
        with open(svgPath, 'w') as f:
            f.write(newsvg)
        return svgPath.replace("\\", "/")
    
    @staticmethod
    def parseValueType( value, attrType ):
        """ Converse value type """
        if attrType=='number':
            return float(value)
        return value
    
    def hex2QColor( self, value ):
        return QColor( *self.parseHexColor(value) )
    
    def hex2str( self, value ):
        return '{},{},{},{}'.format( *self.parseHexColor(value) )
    
    @staticmethod
    def parseHexColor( value, qgisString=True ):
        """ Converse HEX colors to RGBA """
        c = value[1:]
        if len(c)==6:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            a = 255
        elif len(c) == 8:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            a = int(c[6:8], 16)
        return r, g, b, a
    
    @staticmethod
    def parseTransparency( value ):
        """ Convert transparency value from 0-1 range to percent """
        return (1-value)*100

class RasterItem(LayerItem):
    
    def __init__(self, data, parent=None):
        super(RasterItem, self).__init__(data, parent)
        self.extent = data.get('visual', {}).get('extent')
        self.icon = QIcon(':/plugins/DiviPlugin/images/raster.png')
    
    def identifier(self):
        return 'raster@%s' % self.id
    
    def getUri(self, token):
        uri = 'url=%s/tiles/%s/%s/{z}/{x}/{y}.png?token=%s' % (DIVI_HOST, self.parent().id, self.id, token)
        return '%s&type=xyz&zmax=20' %  str(QgsDataSourceURI(uri).encodedUri())

class WmsItem(LayerItem):
    
    def __init__(self, data, parent=None):
        super(WmsItem, self).__init__(data, parent)
        self.icon = QIcon(':/plugins/DiviPlugin/images/wms.png')
        self.params = data['visual']
    
    def identifier(self):
        return 'wms@%s' % self.id
    
    def getUri(self):
        return 'url={url}&format={format}&layers={layer}&styles='.format( **self.params )

class DiviModel(QAbstractItemModel):
    
    def __init__(self, parent=None):
        super(DiviModel, self).__init__(parent)
        
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
        elif role == Qt.FontRole:
            font = QFont()
            if isinstance(item, LayerItem):
                font.setBold(bool(item.items))
            elif isinstance(item, ProjectItem):
                font.setItalic( item.loadedChilds() )
                font.setUnderline( item.loadedChilds() )
            return font
        elif role == Qt.ToolTipRole:
            return item.abstract
        elif role == Qt.UserRole:
            #Return item itself
            return item
        elif role == Qt.UserRole+1:
            return item.identifier()
        elif role == Qt.UserRole+2:
            return item.metaObject().className()
    
    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == 0:
            return self.tr('Data')
        return None
    
    def showLoading(self):
        self.removeAll()
        self.beginInsertRows(QModelIndex(), 0, 0)
        item = LoadingItem( self.rootItem )
        self.endInsertRows()
    
    def addData(self, projects, layers, tables):
        self.removeAll()
        self.beginInsertRows(QModelIndex(), 0, len(projects)-1)
        self.addProjects(projects)
        self.addLayers(layers)
        self.addTables(tables)
        self.endInsertRows()
    
    def addProjects(self, projects):
        for project in projects:
            item = ProjectItem( project, self.rootItem )
    
    def addLayers(self, layers):
        for layer in layers:
            project = self.findItem(layer['id_projects'], 'project')
            if layer['data_type']=='vector':
                item = VectorItem(layer, project )
            elif layer['data_type']=='wms':
                item = WmsItem(layer, project )
            else:
                item = RasterItem(layer, project )
    
    def addTables(self, tables):
        for table in tables:
            project = self.findItem(table['id_projects'], 'project')
            item = TableItem(table, project )
    
    def addProjectItems(self, project, layers=[], tables=[]):
        parent = self.findItem(project.id, 'project', True)
        count = len(project.childItems)
        self.beginInsertRows(parent, count, count+len(layers)+len(tables)-1)
        self.addLayers(layers)
        self.addTables(tables)
        self.endInsertRows()
    
    def removeAll(self):
        item = self.index(0,0).data(Qt.UserRole)
        self.removeRows(0, self.rootItem.childCount(), self.index(0,0).parent())
    
    def removeRows(self, row, count, parent):
        if not parent.isValid():
            item = self.rootItem
        else:
            item = parent.data(Qt.UserRole)
        self.beginRemoveRows(parent, row, count+row-1)
        item.removeChilds()
        self.endRemoveRows()
    
    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parentItem = parent.data(Qt.UserRole) if parent.isValid() else self.rootItem
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        return QModelIndex()
    
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.data(Qt.UserRole)
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        parentItem = parent.data(Qt.UserRole) if parent.isValid() else self.rootItem
        return parentItem.childCount()

    def hasChildren(self, parent):
        parentItem = parent.data(Qt.UserRole) if parent.isValid() else self.rootItem
        return parentItem.childCount() > 0
    
    def findItem(self, oid, item_type='vector', as_model=False):
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

