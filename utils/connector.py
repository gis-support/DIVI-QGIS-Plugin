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

from PyQt4.QtCore import QUrl, QObject, QEventLoop, pyqtSignal, QSettings, \
    QBuffer, qDebug
from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager, \
    QHttpMultiPart, QHttpPart, QNetworkReply, QHttpMultiPart, QHttpPart
from qgis.core import QgsMessageLog, QgsCredentials
from qgis.gui import QgsMessageBar
import json
import ConfigParser
import os.path as op

config = ConfigParser.ConfigParser()
config.read(op.join(op.dirname(__file__),'../metadata.txt'))

PLUGIN_VERSION = config.get('general', 'version')

class DiviConnector(QObject):
    diviLogged = pyqtSignal(str, str)
    downloadingProgress = pyqtSignal(float)
    uploadingProgress = pyqtSignal(float)
    
    DIVI_HOST = 'https://divi.io'
    
    def __init__(self, iface=None, auto_login=True):
        QObject.__init__(self)
        self.iface = iface
        self.auto_login = auto_login
        self.token = QSettings().value('divi/token', None)
    
    #Sending requests to DIVI
    
    def sendRequest(self, endpoint, params, method, data=None, headers={}, as_unicode=True):
        def send(params):
            url = self.formatUrl(endpoint, params)
            request = QNetworkRequest(url)
            headers['User-Agent'] = 'Divi QGIS Plugin/%s' % PLUGIN_VERSION
            for key, value in headers.iteritems():
                request.setRawHeader(key, value)
            if method == 'delete':
                reply = manager.sendCustomRequest(request, 'DELETE', data)
            else:
                if not data:
                    reply = getattr(manager, method)(request)
                else:
                    reply = getattr(manager, method)(request, data)
            loop = QEventLoop()
            reply.uploadProgress.connect(self.uploadProgress)
            reply.downloadProgress.connect(self.downloadProgress)
            #reply.error.connect(self._error)
            reply.finished.connect(loop.exit)
            loop.exec_()
            return reply
        manager = QNetworkAccessManager()
        manager.sslErrors.connect(self._sslError)
        reply = send(params)
        content = reply.readAll()
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if reply.error() == QNetworkReply.ConnectionRefusedError:
            if self.iface is not None:
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    self.trUtf8("Server rejected request"),
                    level=QgsMessageBar.CRITICAL, duration=3)
            return
        elif status_code == 409:
            if self.iface is not None:
                min_version = json.loads(unicode(content)).get('error', '')
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    self.tr("Error 409: DIVI QGIS Plugin is not supported in version '%s'. "
                            "Please upgrade to version '%s' or higher. ") % (PLUGIN_VERSION, min_version),
                    level=QgsMessageBar.CRITICAL, duration=0)
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
        elif status_code == 404:
            if self.iface is not None:
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    self.tr("Error 404: requested resource could not be found "),
                    level=QgsMessageBar.CRITICAL, duration=3)
            return
        elif status_code == 423:
            if self.iface is not None:
                self.iface.messageBar().pushMessage(self.tr("Error"),
                    self.tr("Error 423: requested resource is locked"),
                    level=QgsMessageBar.CRITICAL, duration=3)
            return
        if as_unicode:
            content = unicode(content)
        return content
    
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
        buff.write(json.dumps(data).decode('utf-8'))
        buff.seek(0)
        headers.update({"Content-Type":"application/json"})
        content = self.sendRequest( endpoint, params,
            'delete',
            buff,
            headers=headers
        )
        buff.close()
        return content
    
    def sendGetRequest(self, endpoint, data, as_unicode=True):
        return self.sendRequest(endpoint, data, 'get',
                as_unicode = as_unicode
            )
    
    #Login
    
    def diviLogin(self):
        QgsMessageLog.logMessage('Fetching token', 'DIVI')
        settings = QSettings()
        (success, email, password) = QgsCredentials.instance().get( 
            'Logowanie DIVI', settings.value('divi/email', None), None )
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
        settings.setValue('divi/email', email)
        settings.setValue('divi/token', self.token)
        settings.setValue('divi/status', data['status'])
        settings.setValue('divi/id', data['id'])
        self.diviLogged.emit(email, self.token)
        return self.token
    
    def diviLogout(self):
        self.sendGetRequest('/signout', {'token':self.token})
        QgsMessageLog.logMessage('Disconnected', 'DIVI')
    
    #Fetching data from server
    
    def diviFeatchData(self):
        QgsMessageLog.logMessage('Fecthing data', 'DIVI')
        projects = self.getJson(self.sendGetRequest('/projects', {'token':self.token}))
        if not projects:
            return
        layers, tables = self.diviGetProjectItems()
        return projects['data'], layers, tables
    
    def diviGetProjectItems(self, projectid=None):
        params = {'token':self.token}
        if projectid is not None:
            params['project'] = projectid
        layers = self.getJson(self.sendGetRequest('/layers', params))
        tables = self.getJson(self.sendGetRequest('/tables', params))
        return layers['data'], tables['data']
    
    def diviGetLayerFeatures(self, layerid):
        QgsMessageLog.logMessage('Fecthing layer %s features' % layerid, 'DIVI')
        layer = self.sendGetRequest('/features/%s'%layerid, {'token':self.token, 'geometry':'base64'})
        return self.getJson(layer)
    
    def diviGetTableRecords(self, tableid):
        QgsMessageLog.logMessage('Fecthing table %s records' % tableid, 'DIVI')
        records = self.sendGetRequest('/records/%s'%tableid, {'token':self.token})
        return self.getJson(records)
    
    def diviGetLayer(self, layerid):
        QgsMessageLog.logMessage('Fecthing layer %s' % layerid, 'DIVI')
        layer = self.sendGetRequest('/layers/%s'%layerid, {'token':self.token})
        return self.getJson(layer)
    
    def diviGetTable(self, tableid):
        QgsMessageLog.logMessage('Fecthing table %s' % tableid, 'DIVI')
        table = self.sendGetRequest('/tables/%s'%tableid, {'token':self.token})
        return self.getJson(table)
    
    def getUserPermissions(self, item_type, userid=None):
        if userid is None:
            userid = self.getUserId()
        if userid is None:
            return
        QgsMessageLog.logMessage('Fecthing permissions for user %s' % userid, 'DIVI')
        perms = self.getJson(self.sendGetRequest('/user_%s/%s'%(item_type, userid), {'token':self.token}))
        if not perms:
            return
        return { lyr['id']:lyr.get('editing', 0) for lyr in perms['data'] }
    
    def getUserPermission(self, layerid, item_type, userid=None):
        if userid is None:
            userid = self.getUserId()
        if userid is None:
            return
        if int(QSettings().value('divi/status', 3)) < 3:
            return { layerid : 1 }
        QgsMessageLog.logMessage('Fecthing permissions to %s %s for user %s' % (item_type, layerid, userid), 'DIVI')
        perm = self.getJson(self.sendGetRequest('/user_%ss/%s/%s'%(item_type, userid, layerid), {'token':self.token}))
        if perm:
            return { layerid : perm.get('editing', 0) }
    
    def sendGeoJSON(self, data, filename, projectid, data_format):
        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)
        format_part = QHttpPart()
        format_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="format"')
        format_part.setBody(data_format)
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
        name_part.setBody(filename)
        crs_part = QHttpPart()
        crs_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="srs"')
        crs_part.setBody(str(crs))
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
    
    def getAttachments(self, featureid):
        return self.getJson(self.sendGetRequest('/files', {'token':self.token, 'feature':str(featureid)}))
    
    def getComments(self, featureid):
        return self.getJson(self.sendGetRequest('/comments/%s' % featureid, {'token':self.token}))
    
    def getChanges(self, featureid):
        return self.getJson(self.sendGetRequest('/changes', {'token':self.token, 'feature':str(featureid)}))
    
    def getFile(self, featureid, fileName):
        return self.sendGetRequest('/files/%s/%s' % (featureid, fileName), {'token':self.token}, as_unicode=False)
    
    def getFiles(self, featureid):
        return self.sendGetRequest('/download_files', {'token':self.token, 'ids':str([featureid])}, as_unicode=False)
    
    def addComment(self, featureid, text):
        return self.getJson(
            self.sendPostRequest('/comments/%s'%featureid, {'content': text}, params={'token':self.token})
        )
    
    def sendAttachments(self, featureid, files):
        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)
        for fileName, fileData in files.iteritems():
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
    
    def downloadProgress(self, received, total):
        if total!=0:
            self.downloadingProgress.emit( float(received)/total )
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
        url = QUrl(self.DIVI_HOST + endpoint)
        url.setQueryItems(list(params.iteritems()))
        return url
    
    def getUserId(self):
        settings = QSettings()
        userid = settings.value('divi/id', None)
        if userid is None:
            username = settings.value('divi/email', None)
            users = self.getJson(self.sendGetRequest('/users', {'token':self.token}))
            if not users or username is None:
                return
            for data in users['data']:
                if data['email'] == username:
                    userid = data['id']
                    settings.setValue('divi/id', userid)
                    settings.setValue('divi/status', data['status'])
                    break
            else:
                return
        return userid
    
    @staticmethod
    def getJson(data):
        if data:
            return json.loads(data)
        return []
