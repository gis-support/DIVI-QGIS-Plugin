# -*- coding: utf-8 -*-
"""
/***************************************************************************
 geoemtry utils
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

import locale

class SetLocale_CtxDec(object):
    """ Tymczasowa zmiana ustawień separatora dziesiętnego na kropkę
    w celu poprawnego parsowania GeoJSON przez OGR.
    Klasa może być użyta zarówno jako dekorator jak i contextmanager
    """
    
    def set_locale(self):
        """ Ustawienie kropki jako separatora dziesiętnego """
        self.default_locale = locale.getlocale()
        locale.setlocale(locale.LC_NUMERIC, 'C')
    
    def restore_locale(self):
        """ Przywrócenie domyślnego separatora dziesiętnego """
        locale.setlocale(locale.LC_NUMERIC, self.default_locale)

    def __call__(self, f):
        """ Dekorator """
        def wrapped_f(*args, **kwargs):
            self.set_locale()
            result = f(*args, **kwargs)
            self.restore_locale()
            return result
        return wrapped_f

    def __enter__(self):
        """ Początek contextmanager """
        self.set_locale()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Koniec contextmanager """
        self.restore_locale()
