# -*- coding: utf-8 -*-
"""
/***************************************************************************
 data
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

from PyQt4.QtCore import QVariant
from qgis.core import QgsVectorLayer, QgsMessageLog, QgsMapLayerRegistry, \
    QgsField, QgsFeature, QgsGeometry, QGis

#Map DIVI to QGIS data types, default is string
TYPES_MAP = {
    'number' : QVariant.Double,
}

from .connector import DiviConnector

def loadLayer(mapLayer, node):
    layerid = mapLayer.customProperty('DiviId')
    if layerid is not None:
        connector = DiviConnector()
        layer_meta = connector.diviGetLayer(layerid)
        data = connector.diviGetLayerFeatures(layerid)
        if data:
            if mapLayer.geometryType() == QGis.Point:
                points = mapLayer
                layer = {'points':points}
            elif mapLayer.geometryType() == QGis.Line:
                lines = mapLayer
                layer = {'lines':lines}
            elif mapLayer.geometryType() == QGis.Polygon:
                polygons = mapLayer
                layer = {'polygons':polygons}
            else:
                return
            addFeatures(layerid, data['features'], fields=getFields(layer_meta['fields']), **layer)

def addLayer(features, layer):
    #Layers have CRS==4326
    definition = '?crs=epsg:4326'
    #Create temp layers for point, linestring and polygon geometry types
    points = QgsVectorLayer("MultiPoint"+definition, layer.name, "memory")
    lines = QgsVectorLayer("MultiLineString"+definition, layer.name, "memory")
    polygons = QgsVectorLayer("MultiPolygon"+definition, layer.name, "memory")
    addFeatures(layer.id, features, fields=getFields(layer.fields), points=points, lines=lines, polygons=polygons)

def getFields(fields):
    QgsMessageLog.logMessage(str(fields), 'DIVI')
    return [ QgsField(field['key'], TYPES_MAP.get(field['type'], QVariant.String)) for field in fields ]

def addFeatures(layerid, features, fields, points=None, lines=None, polygons=None):#, layer=None, mapLayer=None):
    """ Add DIVI layer to QGIS """
    QgsMessageLog.logMessage(str(fields), 'DIVI')
    if points:
        points_pr = points.dataProvider()
        if points_pr.fields():
            points_pr.deleteAttributes(range(len(points_pr.fields())))
        points_pr.addAttributes(fields)
        points.updateFields()
    if lines:
        lines_pr = lines.dataProvider()
        if lines_pr.fields():
            lines_pr.deleteAttributes(range(len(lines_pr.fields())))
        lines_pr.addAttributes(fields)
        lines.updateFields()
    if polygons:
        polygons_pr = polygons.dataProvider()
        if polygons_pr.fields():
            polygons_pr.deleteAttributes(range(len(polygons_pr.fields())))
        polygons_pr.addAttributes(fields)
        polygons.updateFields()
    #Lists of QGIS features
    points_list = []
    lines_list = []
    polygons_list = []
    for feature in features:
        geom = QgsGeometry.fromWkt(feature['geometry'])
        f = QgsFeature()
        f.setGeometry(geom)
        f.setAttributes([ feature['properties'].get(field.name()) for field in fields ])
        #Add feature to list by geometry type
        if geom.type() == QGis.Point:
            points_list.append(f)
        elif geom.type() == QGis.Line:
            lines_list.append(f)
        elif geom.type() == QGis.Polygon:
            polygons_list.append(f)
        else:
            continue
    #Add only layers that have features
    if points_list:
        points_pr.addFeatures(points_list)
        points.setCustomProperty('DiviId', layerid)
        QgsMapLayerRegistry.instance().addMapLayer(points)
    if lines_list:
        lines_pr.addFeatures(lines_list)
        lines.setCustomProperty('DiviId', layerid)
        QgsMapLayerRegistry.instance().addMapLayer(lines)
    if polygons_list:
        polygons_pr.addFeatures(polygons_list)
        polygons.setCustomProperty('DiviId', layerid)
        QgsMapLayerRegistry.instance().addMapLayer(polygons)
    #if points_list or lines_list or polygons_list:
    #    layer.loaded = True
