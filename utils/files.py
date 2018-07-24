# -*- coding: utf-8 -*-
"""
/***************************************************************************
 files
                                 A QGIS plugin
 Integracja QGIS z platformą DIVI firmy GIS Support sp. z o. o.
                             -------------------
        begin                : 2016-11-25
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

from PyQt5.QtCore import QFile, QIODevice, QSettings
from PyQt5.QtWidgets import QFileDialog
from os import path as op, remove
from ..config import *
from .commons import translate

def readFile(path, delete_after=False):
    data_file = QFile( path )
    data_file.open(QIODevice.ReadOnly)
    data = data_file.readAll()
    data_file.close()
    if delete_after:
        remove( path )
    return data

def getSavePath(fileName):
    """ get path to save from user """
    ext = op.splitext(fileName)[-1]
    settings = QSettings()
    defaultDir = settings.value('%s/last_dir' % CONFIG_NAME, '')
    defaultPath = op.join(defaultDir, fileName)
    #filePath = QFileDialog.getSaveFileName(None, 'Save file to...',
    filePath = QFileDialog.getSaveFileName(None, translate('Save file to...'),
        defaultPath, filter = ext)
    if not filePath:
        return
    settings.setValue('%s/last_dir' % CONFIG_NAME, op.dirname(filePath))
    return filePath
