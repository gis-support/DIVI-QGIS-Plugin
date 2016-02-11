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

from qgis.core import QgsVectorLayer, QgsMessageLog, QgsMapLayerRegistry, \
    QgsField, QgsFeature, QgsGeometry, QGis

#Map DIVI to QGIS data types, default is string
TYPES_MAP = {
    'number' : 'double',
}

def addLayer(features, layer):
    """ Add DIVI layer to QGIS """
    fields_def = '&'.join( 'field=%s:%s' % (field['key'], TYPES_MAP.get(field['type'], 'string')) for field in layer.fields )
    #Layers have CRS==4326
    definition = '?crs=epsg:4326&'+fields_def
    #Create temp layers for point, linestring and polygon geometry types
    points = QgsVectorLayer("MultiPoint"+definition, layer.name, "memory")
    points_pr = points.dataProvider()
    lines = QgsVectorLayer("MultiLineString"+definition, layer.name, "memory")
    lines_pr = lines.dataProvider()
    polygons = QgsVectorLayer("MultiPolygon"+definition, layer.name, "memory")
    polygons_pr = polygons.dataProvider()
    #Lists of QGIS features
    points_list = []
    lines_list = []
    polygons_list = []
    for feature in features:
        geom = QgsGeometry.fromWkt(feature['geometry'])
        f = QgsFeature()
        f.setGeometry(geom)
        f.setAttributes([ feature['properties'].get(field['key']) for field in layer.fields ])
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
        QgsMapLayerRegistry.instance().addMapLayer(points)
    if lines_list:
        lines_pr.addFeatures(lines_list)
        QgsMapLayerRegistry.instance().addMapLayer(lines)
    if polygons_list:
        polygons_pr.addFeatures(polygons_list)
        QgsMapLayerRegistry.instance().addMapLayer(polygons)
    if points_list or lines_list or polygons_list:
        layer.loaded = True
