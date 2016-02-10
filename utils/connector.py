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
    QHttpMultiPart, QHttpPart
from qgis.core import QgsMessageLog, QgsCredentials
import json

class DiviConnector(QObject):
    tokenSetted = pyqtSignal(str)
    
    DIVI_HOST = 'https://divi.io'
    #DIVI_HOST = 'http://0.0.0.0:5034'
    
    def __init__(self):
        QObject.__init__(self)
        self.token = QSettings().value('divi/token', None)
    
    #Sending requests to DIVI
    
    def sendRequest(self, url, method, data=None, headers={}):
        manager = QNetworkAccessManager()
        manager.sslErrors.connect(self._sslError)
        request = QNetworkRequest(url)
        for key, value in headers.iteritems():
            request.setRawHeader(key, value)
        if not data:
            reply = getattr(manager, method)(request)
        else:
            reply = getattr(manager, method)(request, data)
        loop = QEventLoop()
        #reply.downloadProgress.connect(self.progressCB)
        reply.error.connect(self._error)
        reply.finished.connect(loop.exit)
        loop.exec_()
        return unicode(reply.readAll())
    
    def sendPostRequest(self, endpoint, data):
        return self.sendRequest( self.formatUrl(endpoint),
                'post',
                json.dumps(data),
                {"Content-Type":"application/json", "User-Agent":"Divi QGIS Plugin"},
            )
    
    def sendGetRequest(self, endpoint, data):
        url = self.formatUrl(endpoint, data)
        return self.sendRequest(url, 'get',
                headers={"User-Agent":"Divi QGIS Plugin"}
            )
    
    #Login
    
    def diviLogin(self, ):
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
        self.tokenSetted.emit(self.token)
        return self.token
    
    #Fetching data from server
    
    def diviFeatchData(self):
        QgsMessageLog.logMessage('Fecthing data', 'DIVI')
        if not self.token:
            result = self.diviLogin()
            QgsMessageLog.logMessage('login: '+result, 'DIVI')
            if not result:
                return
        accounts = json.loads(self.sendGetRequest('/accounts', {'token':self.token}))
        projects = json.loads(self.sendGetRequest('/projects', {'token':self.token}))
        layers = json.loads(self.sendGetRequest('/layers', {'token':self.token}))
        return accounts['data'], projects['data'], layers['data']
    
    #Helpers
    
    def _error(self, error):
        QgsMessageLog.logMessage(str(error), 'DIVI', QgsMessageLog.CRITICAL)
    
    def _sslError(self, reply, errors):
        reply.ignoreSslErrors()
    
    def formatUrl(self, endpoint, params={}):
        url = QUrl(self.DIVI_HOST + endpoint)
        url.setQueryItems(list(params.iteritems()))
        return url
