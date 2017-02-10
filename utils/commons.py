# -*- coding: utf-8 -*-
"""
/***************************************************************************
 utils
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

from PyQt4.QtCore import QDate, Qt, QCoreApplication
from contextlib import contextmanager
import json

class DiviJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, QPyNullVariant):
            return None
        elif isinstance(obj, QDate):
            return obj.toString(Qt.ISODate)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)

@contextmanager
def Cache(plugin):
    plugin.cache = {}
    yield
    plugin.cache = {}

def translate( message ):
    return QCoreApplication.translate('DiviPlugin', message)
