# -*- coding: utf-8 -*-
"""
/***************************************************************************
 rasters
                                 A QGIS plugin
 Integracja QGIS z platformą DIVI firmy GIS Support sp. z o. o.
                             -------------------
        begin                : 2017-02-10
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

from PyQt5.QtWidgets import QProgressDialog
from qgis.core import QgsRasterFileWriter
import os.path as op
from tempfile import NamedTemporaryFile
from .files import readFile

def raster2tiff( layer ):
    """ Convert raster layer to GeoTIFF and return as stream """
    with NamedTemporaryFile() as f:
        #Show raster copy progress
        #feedback = QgsFeedback
        #progress = QProgressDialog()
        writer = QgsRasterFileWriter( f.name )
        writer.setCreateOptions(['COMPRESS=DEFLATE'])
        writer.writeRaster( layer.pipe(), layer.width(), layer.height(), layer.dataProvider().extent(), layer.crs())
        del writer
        #del progress
        data = readFile( f.name )
    return data
