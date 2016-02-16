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

from PyQt4.QtCore import QUrl, QObject, QEventLoop, pyqtSignal, QSettings
from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager, \
    QHttpMultiPart, QHttpPart, QNetworkReply
from qgis.core import QgsMessageLog, QgsCredentials
from qgis.gui import QgsMessageBar
import json

class DiviConnector(QObject):
    diviLogged = pyqtSignal(str, str)
    
    #DIVI_HOST = 'https://divi.io'
    DIVI_HOST = 'http://0.0.0.0:5034'
    
    def __init__(self, iface=None, auto_login=True, progress=None):
        QObject.__init__(self)
        self.iface = iface
        self.auto_login = auto_login
        self.progress = progress
        self.token = QSettings().value('divi/token', None)
    
    #Sending requests to DIVI
    
    def sendRequest(self, endpoint, params, method, data=None, headers={}):
        def send(params):
            url = self.formatUrl(endpoint, params)
            request = QNetworkRequest(url)
            for key, value in headers.iteritems():
                request.setRawHeader(key, value)
            if not data:
                reply = getattr(manager, method)(request)
            else:
                reply = getattr(manager, method)(request, data)
            loop = QEventLoop()
            reply.downloadProgress.connect(self.downloadProgress)
            #reply.error.connect(self._error)
            reply.finished.connect(loop.exit)
            loop.exec_()
            return reply
        manager = QNetworkAccessManager()
        manager.sslErrors.connect(self._sslError)
        reply = send(params)
        content = unicode(reply.readAll())
        #reply.downloadProgress.disconnect(self.downloadProgress)
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
        #reply.downloadProgress.disconnect(self.downloadProgress)
        return content
    
    def sendPostRequest(self, endpoint, data, params={}):
        return self.sendRequest( endpoint, params,
                'post',
                json.dumps(data),
                {"Content-Type":"application/json", "User-Agent":"Divi QGIS Plugin"},
            )
    
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
        data = json.loads(content)
        self.token = data['token']
        settings.setValue('divi/email', email)
        settings.setValue('divi/token', self.token)
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
    
    def diviGetLayer(self, layerid):
        QgsMessageLog.logMessage('Fecthing layer %s' % layerid, 'DIVI')
        layer = self.sendGetRequest('/layers/%s'%layerid, {'token':self.token})
        return self.getJson(layer)
    
    #Helpers
    
    def downloadProgress(self, received, total):
        if self.progress is not None:
            self.progress.setValue(self.progress.value()+int(20*received/total))
    
    def _sslError(self, reply, errors):
        reply.ignoreSslErrors()
    
    def formatUrl(self, endpoint, params={}):
        url = QUrl(self.DIVI_HOST + endpoint)
        url.setQueryItems(list(params.iteritems()))
        return url
    
    @staticmethod
    def getJson(data):
        if data:
            return json.loads(data)
        return []
