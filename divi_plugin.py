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
    QVariant, QObject, QPyNullVariant
from PyQt4.QtGui import QAction, QIcon
from qgis.core import QgsProject, QGis, QgsVectorLayer, QgsMessageLog,\
    QgsMapLayerRegistry, QgsField, QgsFeature, QgsGeometry, QgsFeatureRequest
# Initialize Qt resources from file resources.py
import resources

# Import the code for the DockWidget
from dialogs.dockwidget import DiviPluginDockWidget
import os.path
from functools import partial

from .utils.connector import DiviConnector
from .utils.widgets import ProgressMessageBar

class DiviPlugin(QObject):
    """QGIS Plugin Implementation."""
    
    TYPES_MAP = {
        'number' : QVariant.Double,
        'calendar' : QVariant.DateTime,
    }
    
    QGIS2DIVI_TYPES_MAP = {
        'number' : (QVariant.Int, QVariant.Double, QVariant.UInt, QVariant.ULongLong),
        'date' : (QVariant.Date, QVariant.DateTime)
    }

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        super(DiviPlugin, self).__init__()
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

        self.msgBar = None
        self.ids_map = {}


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
        callback=None,
        action=None,
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

        if action is None:
            action = QAction(icon, text, parent)
        else:
            action.setIcon(QIcon(icon_path))
            action.setText(text)
        if callback is not None:
            action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addWebToolBarIcon(action)

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
        self.dockwidget = DiviPluginDockWidget(self)
        
        self.add_action(
            icon_path,
            text=self.tr(u'DIVI QGIS Plugin'),
            action = self.dockwidget.toggleViewAction(),
            parent=self.iface.mainWindow())
        
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)

    #--------------------------------------------------------------------------
    
    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD DiviPlugin"
        
        QgsProject.instance().readMapLayer.disconnect(self.loadLayer)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect( self.dockwidget.layersRemoved )

        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&DIVI QGIS Plugin'),
                action)
            # remove icon from toolbar
            self.iface.removeWebToolBarIcon(action)
        self.iface.removeDockWidget(self.dockwidget)

    #--------------------------------------------------------------------------
    
    def loadLayer(self, mapLayer, node=None, add_empty=False):
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
                    layer = {'points':mapLayer}
                elif mapLayer.geometryType() == QGis.Line:
                    layer = {'lines':mapLayer}
                elif mapLayer.geometryType() == QGis.Polygon:
                    layer = {'polygons':mapLayer}
                else:
                    return
                self.msgBar.setBoundries(50, 50)
                permissions = connector.getUserLayersPermissions()
                self.addFeatures(layerid, data['features'], fields=layer_meta['fields'],permissions=permissions,add_empty=add_empty,**layer)
            self.msgBar.progress.setValue(100)
            self.msgBar.close()
            self.msgBar = None
        if self.dockwidget is not None:
            self.dockwidget.getLoadedDiviLayers([mapLayer])
    
    def loadLayerType(self, item, geom_type):
        layer = QgsVectorLayer("%s?crs=epsg:4326" % geom_type, item.name, "memory")
        layer.setCustomProperty('DiviId', item.id)
        self.loadLayer(layer, add_empty=True)
    
    def addLayer(self, features, layer, permissions):
        #Layers have CRS==4326
        definition = '?crs=epsg:4326'
        #Create temp layers for point, linestring and polygon geometry types
        points = QgsVectorLayer("MultiPoint"+definition, layer.name, "memory")
        lines = QgsVectorLayer("MultiLineString"+definition, layer.name, "memory")
        polygons = QgsVectorLayer("MultiPolygon"+definition, layer.name, "memory")
        return self.addFeatures(layer.id, features, fields=layer.fields,
            points=points, lines=lines, polygons=polygons, permissions=permissions)
    
    def addFeatures(self, layerid, features, fields, points=None, lines=None, polygons=None, permissions={}, add_empty=False):
        """ Add DIVI layer to QGIS """
        qgis_fields = [ QgsField(field['key'], self.TYPES_MAP.get(field['type'], QVariant.String)) for field in fields ]
        if points:
            points_pr = points.dataProvider()
            if points_pr.fields():
                points_pr.deleteAttributes(range(len(points_pr.fields())))
            points_pr.addAttributes(qgis_fields)
            points.updateFields()
        if lines:
            lines_pr = lines.dataProvider()
            if lines_pr.fields():
                lines_pr.deleteAttributes(range(len(lines_pr.fields())))
            lines_pr.addAttributes(qgis_fields)
            lines.updateFields()
        if polygons:
            polygons_pr = polygons.dataProvider()
            if polygons_pr.fields():
                polygons_pr.deleteAttributes(range(len(polygons_pr.fields())))
            polygons_pr.addAttributes(qgis_fields)
            polygons.updateFields()
        #Lists of QGIS features
        points_list = []
        lines_list = []
        polygons_list = []
        count = float(len(features))
        points_ids = []
        lines_ids = []
        polygons_ids = []
        for i, feature in enumerate(features, start=1):
            geom = QgsGeometry.fromWkt(feature['geometry'])
            f = QgsFeature()
            f.setGeometry(geom)
            f.setAttributes([ feature['properties'].get(field['key']) for field in fields ])
            #Add feature to list by geometry type
            if geom.type() == QGis.Point:
                points_list.append(f)
                points_ids.append(feature['id'])
            elif geom.type() == QGis.Line:
                lines_list.append(f)
                lines_ids.append(feature['id'])
            elif geom.type() == QGis.Polygon:
                polygons_list.append(f)
                polygons_ids.append(feature['id'])
            else:
                continue
            if self.msgBar is not None:
                self.msgBar.setProgress(i/count)
        #Add only layers that have features
        result = []
        register = partial(self.registerLayer, layerid=layerid, permissions=permissions, addToMap=True)
        if points is not None and (points_list or add_empty):
            result.append(register(layer=points, features=points_list))
            self.ids_map[points.id()] = dict(zip(points.allFeatureIds(), points_ids))
            for i, field in enumerate(fields):
                points.addAttributeAlias(i, field['name'])
        if lines is not None and (lines_list or add_empty):
            result.append(register(layer=lines, features=lines_list))
            self.ids_map[lines.id()] = dict(zip(lines.allFeatureIds(), lines_ids))
            for i, field in enumerate(fields):
                lines.addAttributeAlias(i, field['name'])
        if polygons is not None and (polygons_list or add_empty):
            result.append(register(layer=polygons, features=polygons_list))
            self.ids_map[polygons.id()] = dict(zip(polygons.allFeatureIds(), polygons_ids))
            for i, field in enumerate(fields):
                polygons.addAttributeAlias(i, field['name'])
        return result
    
    def registerLayer(self, layer, layerid, features, permissions, addToMap):
        layer.dataProvider().addFeatures(features)
        layer.setCustomProperty('DiviId', layerid)
        if int(QSettings().value('divi/status', 3)) > 2:
            layer.setReadOnly( not bool(permissions.get(layerid, False)) )
        if not layer.isReadOnly():
            layer.beforeCommitChanges.connect(self.onLayerCommit)
            layer.committedFeaturesAdded.connect(self.onFeaturesAdded)
        if addToMap:
            QgsMapLayerRegistry.instance().addMapLayer(layer)
        return layer
    
    def onLayerCommit(self):
        layer = self.sender()
        layerid = layer.id()
        divi_id = layer.customProperty('DiviId')
        QgsMessageLog.logMessage(self.tr('Zapisywanie warstwy %s') % layer.name(), 'DIVI')
        editBuffer = layer.editBuffer()
        ids_map = self.ids_map[layerid]
        item = self.dockwidget.findLayerItem(divi_id)
        connector = DiviConnector()
        #Added/removed fields
        added_fields = editBuffer.addedAttributes()
        removed_fields = editBuffer.deletedAttributeIds()
        if added_fields or removed_fields:
            if len(item.items) > 1:
                self.iface.messageBar.pushMessage(self.trUtf8("Uwaga:"),
                    self.trUtf8("Zmieniono strukturę jednej warstwy z wczytanych %d powiązanych z wybraną warstwą DIVI. "
                        "Wczytaj ponownie warstwy aby zaktualizować ich strukturę.") % (len(item.items),),
                    level=QgsMessageBar.WARNING)
            fields = item.fields[:]
            for fid in sorted(removed_fields, reverse=True):
                fields.pop(fid)
            for field in added_fields:
                if field.type() in self.QGIS2DIVI_TYPES_MAP['number']:
                    _type = 'number'
                elif field.type() in self.QGIS2DIVI_TYPES_MAP['date']:
                    _type = 'calendar'
                else:
                    _type = 'text'
                fields.append({
                    'key':field.name(),
                    'name':field.name(),
                    'type':_type
                })
            response = connector.updateLayer(divi_id, {'fields':fields})
            updated_layer = response.get('layer')
            if updated_layer:
                for new, old in zip(updated_layer['fields'], fields):
                    if new['key'] != old['key']:
                        item.fields_mapper[old['key']] = new['key']
                item.fields = updated_layer['fields']
        #Deleted features
        deleted = editBuffer.deletedFeatureIds()
        if deleted:
            fids = [ ids_map[fid] for fid in deleted ]
            result = connector.deleteFeatures(divi_id, fids)
            deleted_ids = result['deleted']
            if len(set(fids).symmetric_difference(set(deleted_ids))):
                self.iface.messageBar().pushMessage('BŁĄD',
                    self.trUtf8(u'Podczas usuwania obiektów wystąpił błąd. Nie wszystkie obiekty zostały usunięcte'),
                    self.iface.messageBar().CRITICAL,
                    duration = 3
                )
                return
            else:
                for oid in deleted:
                    ids_map.pop(oid, None)
        #Changed features
        changedAttributes = editBuffer.changedAttributeValues()
        changedGeometries = editBuffer.changedGeometries()
        fids = list(set(changedAttributes.keys()+changedGeometries.keys()))
        if fids:
            data = []
            request = QgsFeatureRequest().setFilterFids(fids)
            for f in layer.getFeatures(request):
                geojson = f.__geo_interface__
                geojson['properties'] = self.map_attributes(geojson['properties'], item.fields_mapper)
                geojson['id'] = ids_map[f.id()]
                data.append(geojson)
            result = connector.changeFeatures(divi_id, data)
    
    def onFeaturesAdded(self, layerid, features):
        layer = QgsMapLayerRegistry.instance().mapLayer(layerid)
        QgsMessageLog.logMessage(self.tr('Zapisywanie obiektów do warstwy %s') % layer.name(), 'DIVI')
        divi_id = layer.customProperty('DiviId')
        item = self.dockwidget.findLayerItem(divi_id)
        geojson_features = []
        ids = []
        for feature in features:
            geojson = feature.__geo_interface__
            geojson['properties'] = self.map_attributes(geojson['properties'], item.fields_mapper)
            geojson_features.append(geojson)
            ids.append(feature.id())
        addedFeatures = {u'type': u'FeatureCollection', u'features': geojson_features }
        connector = DiviConnector()
        result = connector.addNewFeatures(divi_id, addedFeatures)
        if len(ids) != len(result['inserted']):
            self.iface.messageBar().pushMessage('BŁĄD',
                self.trUtf8(u'Podczas dodawania nowych obiektów wystąpił błąd. Nie wszystkie obiekty zostały dodane'),
                self.iface.messageBar().CRITICAL,
                duration = 3
            )
        else:
            self.ids_map[layerid].update({ qgis_id:divi_id for qgis_id,divi_id in zip(ids, result['inserted']) })
    
    def updateDownloadProgress(self, value):
        if self.msgBar is not None:
            self.msgBar.setProgress(value)
    
    @staticmethod
    def map_attributes(attributes, fields_mapper):
        new_attributes = {}
        for key, value in attributes.iteritems():
            if key in fields_mapper:
                key = fields_mapper[key]
            if isinstance(value, QPyNullVariant):
                new_attributes[key] = None
            else:
                new_attributes[key] = value
        return new_attributes
