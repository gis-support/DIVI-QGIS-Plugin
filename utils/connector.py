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

class DiviConnector(QObject):
    diviLogged = pyqtSignal(str, str)
    downloadingProgress = pyqtSignal(float)
    uploadingProgress = pyqtSignal(float)
    
    #DIVI_HOST = 'https://divi.io'
    DIVI_HOST = 'http://0.0.0.0:5034'
    #DIVI_HOST = 'http://dev.apps.divi.pl:5034'
    
    def __init__(self, iface=None, auto_login=True):
        QObject.__init__(self)
        self.iface = iface
        self.auto_login = auto_login
        self.token = QSettings().value('divi/token', None)
    
    #Sending requests to DIVI
    
    def sendRequest(self, endpoint, params, method, data=None, headers={}):
        def send(params):
            url = self.formatUrl(endpoint, params)
            request = QNetworkRequest(url)
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
        content = unicode(reply.readAll())
        if reply.error() == QNetworkReply.ConnectionRefusedError:
            if self.iface is not None:
                self.iface.messageBar().pushMessage(self.trUtf8("Błąd"),
                    self.trUtf8("Serwer odrzucił żądanie"),
                    level=QgsMessageBar.CRITICAL, duration=3)
            return
        elif reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 403:
            if not self.auto_login:
                return
            #Invalid token, try to login and fetch data again
            result = self.diviLogin()
            if not result:
                return
            #Set new token
            params['token'] = result
            reply = send(params)
            content = unicode(reply.readAll())
        elif reply.error() == QNetworkReply.ContentNotFoundError:
            if self.iface is not None:
                self.iface.messageBar().pushMessage(self.trUtf8("Błąd"),
                    self.trUtf8("Błąd 404: nie znaleziono żądanego zasobu"),
                    level=QgsMessageBar.CRITICAL, duration=3)
            return
        return content
    
    def sendPostRequest(self, endpoint, data, params={}):
        return self.sendRequest( endpoint, params,
                'post',
                json.dumps(data),
                {"Content-Type":"application/json", "User-Agent":"Divi QGIS Plugin"},
            )
    
    def sendPutRequest(self, endpoint, data, params={}):
        return self.sendRequest( endpoint, params,
                'put',
                json.dumps(data),
                {"Content-Type":"application/json", "User-Agent":"Divi QGIS Plugin"},
            )
    
    def sendDeleteRequest(self, endpoint, data, params={}):
        buff = QBuffer()
        buff.open(QBuffer.ReadWrite)
        buff.write(json.dumps(data).decode('utf-8'))
        buff.seek(0)
        content = self.sendRequest( endpoint, params,
            'delete',
            buff,
            {"Content-Type":"application/json", "User-Agent":"Divi QGIS Plugin"},
        )
        buff.close()
        return content
    
    def sendGetRequest(self, endpoint, data):
        return self.sendRequest(endpoint, data, 'get',
                headers={"User-Agent":"Divi QGIS Plugin"}
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
                'password' : password
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
    
    #Fetching data from server
    
    def diviFeatchData(self):
        QgsMessageLog.logMessage('Fecthing data', 'DIVI')
        accounts = self.getJson(self.sendGetRequest('/accounts', {'token':self.token}))
        if not accounts:
            return
        projects = self.getJson(self.sendGetRequest('/projects', {'token':self.token}))
        layers = self.getJson(self.sendGetRequest('/layers', {'token':self.token}))
        tables = self.getJson(self.sendGetRequest('/tables', {'token':self.token}))
        return accounts['data'], projects['data'], layers['data'], tables['data']
    
    def diviGetLayerFeatures(self, layerid):
        QgsMessageLog.logMessage('Fecthing layer %s features' % layerid, 'DIVI')
        layer = self.sendGetRequest('/features/%s'%layerid, {'token':self.token, 'geometry':'wkt'})
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
            multi_part,
            {"User-Agent":"Divi QGIS Plugin"}
        )
        return json.loads(content)
    
    #Edit data
    
    def addNewFeatures(self, layerid, data):
        content = self.sendPostRequest('/features/%s'%layerid, data, params={'token':self.token})
        return self.getJson(content)
    
    def deleteFeatures(self, layerid, fids):
        QgsMessageLog.logMessage('Removing objects: '+str(fids), 'DIVI')
        content = self.sendDeleteRequest('/features/%s'%layerid, {'features':fids}, params={'token':self.token})
        return self.getJson(content)
    
    def changeFeatures(self, layerid, data):
        QgsMessageLog.logMessage('Saving changed objects', 'DIVI')
        content = self.sendPutRequest('/features/%s'%layerid, {'features':data}, params={'token':self.token})
        return self.getJson(content)
    
    def updateLayer(self, layerid, data):
        QgsMessageLog.logMessage('Saving changed layer %s' % layerid, 'DIVI')
        content = self.sendPutRequest('/layers/%s'%layerid, data, params={'token':self.token})
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
