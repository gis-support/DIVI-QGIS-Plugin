# coding=utf-8
"""DockWidget test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'info@gis-support.pl'
__date__ = '2016-02-09'
__copyright__ = 'Copyright 2016, GIS Support sp. z o. o.'

import unittest

from PyQt4.QtGui import QDockWidget

from divi_plugin_dockwidget import DiviPluginDockWidget

from utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class DiviPluginDockWidgetTest(unittest.TestCase):
    """Test dockwidget works."""

    def setUp(self):
        """Runs before each test."""
        self.dockwidget = DiviPluginDockWidget(None)

    def tearDown(self):
        """Runs after each test."""
        self.dockwidget = None

    def test_dockwidget_ok(self):
        """Test we can click OK."""
        pass

if __name__ == "__main__":
    suite = unittest.makeSuite(DiviPluginDialogTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

