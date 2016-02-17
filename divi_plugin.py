# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiviPlugin
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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt,\
    QVariant
from PyQt4.QtGui import QAction, QIcon
from qgis.core import QgsProject, QGis, QgsVectorLayer, QgsMessageLog,\
    QgsMapLayerRegistry, QgsField, QgsFeature, QgsGeometry
# Initialize Qt resources from file resources.py
import resources

# Import the code for the DockWidget
from dialogs.dockwidget import DiviPluginDockWidget
import os.path

from .utils.connector import DiviConnector
from .utils.widgets import ProgressMessageBar

class DiviPlugin:
    """QGIS Plugin Implementation."""
    
    TYPES_MAP = {
        'number' : QVariant.Double,
    }

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'DiviPlugin_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&DIVI QGIS Plugin')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'DiviPlugin')
        self.toolbar.setObjectName(u'DiviPlugin')

        #print "** INITIALIZING DiviPlugin"

        self.pluginIsActive = False
        self.dockwidget = None
        
        self.msgBar = None


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('DiviPlugin', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        
        QgsProject.instance().readMapLayer.connect(self.loadLayer)
        
        icon_path = ':/plugins/DiviPlugin/images/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'DIVI'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING DiviPlugin"

        # disconnects
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect( self.dockwidget.layersRemoved )
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD DiviPlugin"
        
        QgsProject.instance().readMapLayer.disconnect(self.loadLayer)

        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&DIVI QGIS Plugin'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING DiviPlugin"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = DiviPluginDockWidget(self)

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
    
    def loadLayer(self, mapLayer, node):
        layerid = mapLayer.customProperty('DiviId')
        if layerid is not None:
            self.msgBar = ProgressMessageBar(self.iface, self.tr(u"Pobieranie warstwy '%s'...")%mapLayer.name())
            connector = DiviConnector()
            connector.downloadingProgress.connect(self.updateDownloadProgress)
            self.msgBar.progress.setValue(10)
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
                self.msgBar.setBoundries(50, 50)
                self.addFeatures(layerid, data['features'], fields=self.getFields(layer_meta['fields']),**layer)
            self.msgBar.progress.setValue(100)
            self.msgBar.close()
            self.msgBar = None
        if self.dockwidget is not None:
            self.dockwidget.getLoadedDiviLayers([mapLayer])
    
    def addLayer(self, features, layer):
        #Layers have CRS==4326
        definition = '?crs=epsg:4326'
        #Create temp layers for point, linestring and polygon geometry types
        points = QgsVectorLayer("MultiPoint"+definition, layer.name, "memory")
        lines = QgsVectorLayer("MultiLineString"+definition, layer.name, "memory")
        polygons = QgsVectorLayer("MultiPolygon"+definition, layer.name, "memory")
        return self.addFeatures(layer.id, features, fields=self.getFields(layer.fields),
            points=points, lines=lines, polygons=polygons)
    
    def getFields(self, fields):
        return [ QgsField(field['key'], self.TYPES_MAP.get(field['type'], QVariant.String)) for field in fields ]

    def addFeatures(self, layerid, features, fields, points=None, lines=None, polygons=None):
        """ Add DIVI layer to QGIS """
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
        count = float(len(features))
        for i, feature in enumerate(features):
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
            if self.msgBar is not None:
                self.msgBar.setProgress(i/count)
        #Add only layers that have features
        result = []
        if points_list:
            points_pr.addFeatures(points_list)
            points.setCustomProperty('DiviId', layerid)
            QgsMapLayerRegistry.instance().addMapLayer(points)
            result.append(points)
        if lines_list:
            lines_pr.addFeatures(lines_list)
            lines.setCustomProperty('DiviId', layerid)
            QgsMapLayerRegistry.instance().addMapLayer(lines)
            result.append(lines)
        if polygons_list:
            polygons_pr.addFeatures(polygons_list)
            polygons.setCustomProperty('DiviId', layerid)
            QgsMapLayerRegistry.instance().addMapLayer(polygons)
            result.append(polygons)
        return result
    
    def updateDownloadProgress(self, value):
        if self.msgBar is not None:
            self.msgBar.setProgress(value)
