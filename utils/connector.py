# -*- coding: utf-8 -*-
"""
/***************************************************************************
 diviConnector
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

from PyQt5.QtCore import QUrl, QUrlQuery, QObject, QEventLoop, pyqtSignal, QSettings, \
    QBuffer, qDebug
from PyQt5.QtNetwork import QNetworkRequest, QHttpMultiPart, QHttpPart, \
    QNetworkReply, QHttpMultiPart, QHttpPart
from qgis.core import QgsMessageLog, QgsCredentials, Qgis, QgsNetworkAccessManager
from qgis.gui import QgsMessageBar
import json
import configparser
import os.path as op
from ..config import *

config = configparser.ConfigParser()
config.read(op.join(op.dirname(__file__),'../metadata.txt'))

PLUGIN_VERSION = config.get('general', 'version')

class DiviConnector(QObject):
    diviLogged = pyqtSignal(str, str)
    downloadingProgress = pyqtSignal(float)
    uploadingProgress = pyqtSignal(float)
    abort_sig = pyqtSignal()
    
    def __init__(self, iface=None, auto_login=True):
        QObject.__init__(self)
        self.total = -1
        self.aborted = False
        self.iface = iface
        self.auto_login = auto_login
        self.token = QSettings().value('%s/token' % CONFIG_NAME, None)
    
    #Sending requests to DIVI
    
    def sendRequest(self, endpoint, params, method, data=None, headers={}, as_str=True):
        def send(params):
            url = self.formatUrl(endpoint, params)
            request = QNetworkRequest(url)
            headers['User-Agent'] = 'Divi QGIS Plugin/%s' % PLUGIN_VERSION
            QgsMessageLog.logMessage(str(headers), 'DIVI')
            for key, value in headers.items():
                request.setRawHeader(key.encode('utf-8'), value.encode('utf-8'))
            if method == 'delete':
                reply = manager.sendCustomRequest(request, 'DELETE'.encode('utf-8'), data)
            else:
                if not data:
                    reply = getattr(manager, method)(request)
                elif isinstance(data, QHttpMultiPart) == True:
                    reply = getattr(manager, method)(request, data)
                elif isinstance(data, str) == True:
                    reply = getattr(manager, method)(request, data.encode('utf-8'))
            loop = QEventLoop()
            reply.uploadProgress.connect(self.uploadProgress)
            reply.downloadProgress.connect(self.downloadProgress)
            reply.metaDataChanged.connect(self.metaDataChanged)
            #reply.error.connect(self._error)
            reply.finished.connect(loop.exit)
            self.abort_sig.connect( reply.abort )
            loop.exec_()
            self.abort_sig.disconnect( reply.abort )
            return reply
        manager = QgsNetworkAccessManager()
        manager.sslErrors.connect(self._sslError)
        reply = send(params)

        content = reply.readAll()
        content = bytearray(content)
        content = bytes(content)
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if reply.error() == QNetworkReply.ConnectionRefusedError:
            if self.iface is not None:
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    self.tr("Server rejected request"),
                    level=Qgis.Critical, duration=3)
            return
        elif status_code == 500:
            if self.iface is not None:
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    self.tr("Error 500: Internal Server Error"),
                    level=Qgis.Critical, duration=0)
            return
        elif status_code == 409:
            if self.iface is not None:
                min_version = json.loads(content.decode()).get('error', '')
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    self.tr("Error 409: DIVI QGIS Plugin is not supported in version '%s'. "
                            "Please upgrade to version '%s' or higher. ") % (PLUGIN_VERSION, min_version),
                    level=Qgis.Critical, duration=0)
            return
        elif status_code == 402:
            if self.iface is not None:
                self.iface.messageBar().pushCritical(self.tr("Error"), self.tr("Error 402: User data limit exceeded"))
            return
        elif status_code == 403:
            if not self.auto_login:
                return
            #Invalid token, try to login and fetch data again
            result = self.diviLogin()
            if not result:
                return
            #Set new token
            params['token'] = result
            reply = send(params)
            content = reply.readAll()
            content = bytearray(content)
            content = bytes(content)
        elif status_code == 404:
            if self.iface is not None:
                msg = self.tr("Error 404: Bad login or password") \
                            if reply.url().path() == '/authenticate' else \
                            self.tr("Error 404: requested resource could not be found ")
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    msg, level=Qgis.Critical, duration=3)
            return
        elif status_code == 423:
            if self.iface is not None:
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    self.tr("Error 423: requested resource is locked"),
                    level=Qgis.Critical, duration=3)
            return
        if as_str:
            content = content.decode()
        return content
    
    def abort(self):
        """ Przerwanie operacji przez użytkownika """
        QgsMessageLog.logMessage(self.tr('Abort operation'), 'DIVI')
        self.abort_sig.emit()
        self.aborted = True
    
    def sendPostRequest(self, endpoint, data, params={}, headers={}):
        headers.update({"Content-Type":"application/json"})
        return self.sendRequest( endpoint, params,
                'post',
                json.dumps(data),
                headers=headers
            )
    
    def sendPutRequest(self, endpoint, data, params={}, headers={}):
        headers.update({"Content-Type":"application/json"})
        return self.sendRequest( endpoint, params,
                'put',
                json.dumps(data),
                headers=headers
            )
    
    def sendDeleteRequest(self, endpoint, data={}, params={}, headers={}):
        buff = QBuffer()
        buff.open(QBuffer.ReadWrite)
        d = json.dumps(data).encode('utf-8')
        buff.write(d)
        buff.seek(0)
        headers.update({"Content-Type":"application/json"})
        content = self.sendRequest( endpoint, params,
            'delete',
            buff,
            headers=headers
        )
        buff.close()
        return content
    
    def sendGetRequest(self, endpoint, data, as_str=True):
        return self.sendRequest(endpoint, data, 'get',
                as_str = as_str
            )
    
    #Login
    
    def diviLogin(self):
        QgsMessageLog.logMessage('Fetching token', 'DIVI')
        settings = QSettings()
        (success, email, password) = QgsCredentials.instance().get( 
            'Logowanie DIVI', settings.value('%s/email' % CONFIG_NAME, None), None )
        if not success:
            return
        content = self.sendPostRequest('/authenticate', {
                'email': email,
                'password' : password,
                'remember': True
            })
        try:
            data = json.loads(content)
        except TypeError:
            return
        self.token = data['token']
        settings.setValue('%s/email' % CONFIG_NAME, email)
        settings.setValue('%s/token' % CONFIG_NAME, self.token)
        settings.setValue('%s/status' % CONFIG_NAME, data['status'])
        settings.setValue('%s/id' % CONFIG_NAME, data['id'])
        self.diviLogged.emit(email, self.token)
        return self.token
    
    def diviLogout(self):
        self.sendGetRequest('/signout', {'token':self.token})
        QgsMessageLog.logMessage('Disconnected', 'DIVI')
    
    #Fetching data from server
    
    def diviFeatchData(self):
        QgsMessageLog.logMessage('as_str data', 'DIVI')
        projects = self.getJson(self.sendGetRequest('/projects', {'token':self.token}))
        if not projects:
            return
        layers, tables = self.diviGetProjectItems()
        return projects['data'], layers, tables
    
    def diviGetProjectItems(self, projectid=None):
        params = {'token':self.token}
        if projectid is not None:
            params['project'] = projectid
        tables = self.getJson(self.sendGetRequest('/tables', params))
        params['include_wms'] = 'true'
        params['include_basemaps'] = 'true'
        layers = self.getJson(self.sendGetRequest('/layers', params))
        return layers['data'], tables['data']
    
    def diviGetLayerFeatures(self, layerid):
        QgsMessageLog.logMessage('Fetching layer %s features' % layerid, 'DIVI')
        layer = self.sendGetRequest('/features/%s'%layerid, {'token':self.token, 'geometry':'base64'})
        return self.getJson(layer)
    
    def diviGetTableRecords(self, tableid):
        QgsMessageLog.logMessage('Fetching table %s records' % tableid, 'DIVI')
        records = self.sendGetRequest('/records/%s'%tableid, {'token':self.token})
        return self.getJson(records)
    
    def diviGetLayer(self, layerid):
        QgsMessageLog.logMessage('Fetching layer %s' % layerid, 'DIVI')
        layer = self.sendGetRequest('/layers/%s'%layerid, {'token':self.token})
        return self.getJson(layer)
    
    def diviGetTable(self, tableid):
        QgsMessageLog.logMessage('Fetching table %s' % tableid, 'DIVI')
        table = self.sendGetRequest('/tables/%s'%tableid, {'token':self.token})
        return self.getJson(table)

    def getUserPermissions(self, item_type, userid=None):
        if userid is None:
            userid = self.getUserId()
        if userid is None:
            return
        QgsMessageLog.logMessage('Fetching permissions for user %s' % userid, 'DIVI')
        perms = self.getJson(self.sendGetRequest('/user_%s/%s'%(item_type, userid), {'token':self.token}))
        if not perms:
            return
        return { lyr['id']:lyr.get('editing', 0) for lyr in perms['data'] }
    
    def getUserPermission(self, layerid, item_type, userid=None):
        if userid is None:
            userid = self.getUserId()
        if userid is None:
            return
        if int(QSettings().value('%s/status' % CONFIG_NAME, 3)) < 3:
            return { layerid : 1 }
        QgsMessageLog.logMessage('Fetching permissions to %s %s for user %s' % (item_type, layerid, userid), 'DIVI')
        perm = self.getJson(self.sendGetRequest('/user_%ss/%s/%s'%(item_type, userid, layerid), {'token':self.token}))
        if perm:
            return { layerid : perm.get('editing', 0) }
    
    def sendGeoJSON(self, data, filename, projectid, data_format):
        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)
        format_part = QHttpPart()
        format_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="format"')
        format_part.setBody(str(data_format).encode('utf-8'))
        file_part = QHttpPart()
        file_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="file[0]"; filename="%s.sqlite"' % filename)
        file_part.setHeader(QNetworkRequest.ContentTypeHeader, "application/octet-stream")
        file_part.setBody(data)
        multi_part.append(format_part)
        multi_part.append(file_part)
        content = self.sendRequest( '/upload_gis/%s/new' % projectid, {'token':self.token},
            'post',
            multi_part
        )
        return json.loads(content)
    
    def sendRaster(self, data, filename, projectid, crs):
        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)
        name_part = QHttpPart()
        name_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="name"')
        name_part.setBody(filename.encode('utf-8'))
        crs_part = QHttpPart()
        crs_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="srs"')
        crs_part.setBody(str(crs).encode('utf-8'))
        file_part = QHttpPart()
        file_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="file[0]"; filename="%s.tiff"' % filename)
        file_part.setHeader(QNetworkRequest.ContentTypeHeader, "application/octet-stream")
        file_part.setBody(data)
        multi_part.append(name_part)
        multi_part.append(crs_part)
        multi_part.append(file_part)
        content = self.sendRequest( '/rasters/%s' % projectid, {'token':self.token},
            'post',
            multi_part
        )
        if content:
            return json.loads(content)
    
    def startTransaction(self, data_type, layerid):
        QgsMessageLog.logMessage('Starting transaction for %s' % layerid, 'DIVI')
        content = self.sendPostRequest('/transactions/%s'%data_type, {'feature': layerid}, params={'token':self.token})
        if content:
            return self.getJson(content)
    
    def stopTransaction(self, data_type, transaction):
        QgsMessageLog.logMessage('Stopping transaction %s' % transaction, 'DIVI')
        content = self.sendDeleteRequest('/transactions/%s/%s'%(data_type, transaction), params={'token':self.token})
        return self.getJson(content)
    
    def get_attachments(self, featureid):
        QgsMessageLog.logMessage(self.tr('Attachments for %d') % int(featureid), 'DIVI')
        return self.getJson(self.sendGetRequest('/files', {'token':self.token, 'feature':str(featureid)}))
    
    def get_comments(self, featureid):
        QgsMessageLog.logMessage(self.tr('Comments for %s') % featureid, 'DIVI')
        return self.getJson(self.sendGetRequest('/comments/%s' % featureid, {'token':self.token}))
    
    def get_changes(self, featureid):
        QgsMessageLog.logMessage(self.tr('Changes for %d') % featureid, 'DIVI')
        return self.getJson(self.sendGetRequest('/changes', {'token':self.token, 'feature':str(featureid)}))
    
    def getChange(self, cid):
        return self.getJson(self.sendGetRequest('/changes/%s'%cid, {'token':self.token, 'with_geometry':'true'}))
    
    def getFile(self, featureid, fileName, as_thumbnail=False):
        params = {'token':self.token}
        if as_thumbnail:
            params['thumbnail'] = 'true'
        return self.sendGetRequest('/files/%s/%s' % (featureid, fileName), params, as_str=False)
    
    def getFiles(self, featureid):
        return self.sendGetRequest('/download_files', {'token':self.token, 'ids':str([featureid])}, as_str=False)
    
    def addComment(self, featureid, text):
        return self.getJson(
            self.sendPostRequest('/comments/%s'%featureid, {'content': text}, params={'token':self.token})
        )
    
    def sendAttachments(self, featureid, files):
        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)
        for fileName, fileData in files.items():
            file_part = QHttpPart()
            file_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="filedata"; filename="%s"' % fileName)
            file_part.setHeader(QNetworkRequest.ContentTypeHeader, "application/octet-stream")
            file_part.setBody(fileData)
            multi_part.append(file_part)
        content = self.sendRequest( '/upload/%s' % featureid, {'token':self.token},
            'post',
            multi_part
        )
        return json.loads(content)
    
    def removeAttachment(self, featureid, fileName):
        return self.getJson( self.sendDeleteRequest('/files/%s/%s'%(featureid, fileName), params={'token':self.token}) )
    
    def getRasterIdentification(self, layerid, point ):
        return self.getJson( self.sendGetRequest('/sample_raster/%s'%layerid, {'token':self.token, 'locs':'%f %f' % tuple(point) }) )
    
    def downloadRaster( self, rasterid ):
        return self.sendGetRequest('/download_raster/%s'%rasterid, {'token':self.token }, as_str=False)
    
    #Edit data
    
    def addNewFeatures(self, layerid, data, transaction):
        if 'features' in data:
            url = '/features/%s'%layerid
        else:
            url = '/records/%s'%layerid
        content = self.sendPostRequest(url, data,
            params={'token':self.token}, headers={'X-Transaction-Id':transaction})
        return self.getJson(content)
    
    def deleteFeatures(self, layerid, fids, transaction, item_type):
        if item_type == 'vector':
            url = '/features/%s' % layerid
        else:
            url = '/records/%s' % layerid
        QgsMessageLog.logMessage('Removing objects: '+str(fids), 'DIVI')
        content = self.sendDeleteRequest(url, data={'features':fids},
            params={'token':self.token}, headers={'X-Transaction-Id':transaction})
        return self.getJson(content)
    
    def changeFeatures(self, layerid, data, transaction):
        if 'header' in data:
            url = '/records/%s'%layerid
        else:
            url = '/features/%s'%layerid
            data = {'features':data}
        QgsMessageLog.logMessage('Saving changed objects', 'DIVI')
        content = self.sendPutRequest(url, data,
            params={'token':self.token}, headers={'X-Transaction-Id':transaction})
        return self.getJson(content)
    
    def updateLayer(self, layerid, data, transaction=None, item_type='vector'):
        if item_type=='vector':
            QgsMessageLog.logMessage('Saving changed layer %s' % layerid, 'DIVI')
            url = '/layers/%s'%layerid
        else:
            QgsMessageLog.logMessage('Saving changed table %s' % layerid, 'DIVI')
            url = '/tables/%s'%layerid
        headers = {}
        if transaction is not None:
            headers['X-Transaction-Id'] = transaction
        content = self.sendPutRequest(url, data,
            params={'token':self.token}, headers=headers)
        return self.getJson(content)
    
    #Helpers
    
    def metaDataChanged(self):
        reply = self.sender()
        if reply.hasRawHeader(('Content-Length'.encode('utf-8'))):
            content = reply.rawHeader('Content-Length'.encode('utf-8'))
        elif reply.hasRawHeader('Data-Length'.encode('utf-8')):
            content = reply.rawHeader('Data-Length'.encode('utf-8'))
        else:
            self.total = -1
            return
        content = bytes(bytearray(content)).decode()
        #wartość nagłówka może być zdublowana
        spl = content.split(",")
        self.total = int(spl[0])
        

    def downloadProgress(self, received, total):
        if self.total>0:
            self.downloadingProgress.emit( float(received)/self.total )
        else:
            self.downloadingProgress.emit( 1. )
    
    def uploadProgress(self, received, total):
        if total!=0:
            self.uploadingProgress.emit( float(received)/total )
        else:
            self.uploadingProgress.emit( 1. )
    
    def _sslError(self, reply, errors):
        reply.ignoreSslErrors()
    
    def formatUrl(self, endpoint, params={}):
        url = QUrl(DIVI_HOST + endpoint)
        qr = QUrlQuery()
        qr.setQueryItems(list(params.items()))
        url.setQuery( qr )
        return url
    
    def getUserId(self):
        settings = QSettings()
        userid = settings.value('%s/id' % CONFIG_NAME, None)
        if userid is None:
            username = settings.value('%s/email' % CONFIG_NAME, None)
            users = self.getJson(self.sendGetRequest('/users', {'token':self.token}))
            if not users or username is None:
                return
            for data in users['data']:
                if data['email'] == username:
                    userid = data['id']
                    settings.setValue('%s/id' % CONFIG_NAME, userid)
                    settings.setValue('%s/status' % CONFIG_NAME, data['status'])
                    break
            else:
                return
        return userid
    
    @staticmethod
    def getJson(data):
        if data:
            #print(data)
            return json.loads(data)
        return []
