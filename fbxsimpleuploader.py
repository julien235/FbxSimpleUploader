#! /usr/bin/env python

""" Utilitaire d'envoi de fichier sur une freebox """
import base64

import sys
import os
import argparse
import requests
import hmac
import simplejson as json
from hashlib import sha1
import datetime
import time
import atexit


# fbxosupload is a command line utility to upload file to your Freebox.
# Script based on fbxosctrl from Christophe Lherieau (aka Skimpax)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# FreeboxOS API is available here: http://dev.freebox.fr/sdk/os

# Set to True to enable logging to stdout
gVerbose = False

FBXOSCTRL_VERSION = "0.0.1"

__author__ = "Julien Garcia"
__license__ = "GPL"
__version__ = FBXOSCTRL_VERSION
__maintainer__ = "julien235"
__email__ = "julien235@gmail.com"
__status__ = "Development"

# Descriptor of this app presented to FreeboxOS server to be granted
gAppDesc = {
    "app_id": "fr.fbx.upload",
    "app_name": "Fbx Uploader",
    "app_version": FBXOSCTRL_VERSION,
    "device_name": "myDev"
}

def log(what):
    """ Log to stdout if verbose mode is enabled """
    if True == gVerbose:
        print what

def cleanup(val):
    return val

class FbxOSException(Exception):

    """ Exception for FreeboxOS domain """

    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        self._logout()
        return self.reason


class FreeboxOSCtrl:

    """ This class handles connection and dialog with FreeboxOS thanks to
its exposed REST API """

    def __init__(self, fbxAddress="http://mafreebox.freebox.fr",
                 regSaveFile="fbxosctrl_registration.reg"):
        """ Constructor """
        self.fbxAddress = fbxAddress
        self.isLoggedIn = False
        self.registrationSaveFile = regSaveFile
        self.registration = {'app_token': '', 'track_id': None}
        self.challenge = None
        self.sessionToken = None
        self.permissions = None
        # Add extension with date and time to file. Eg: test1.txt.d20160328.t182501
        self.addDateTimeToFile = False
        # Freebox API version
        self.fbxApiVersion  = "v3"
        # Folder on Freebox
        self.targetFoldername = '/Disque 1'

    def _saveRegistrationParams(self):
        """ Save registration parameters (app_id/token) to a local file """
        log(">>> _saveRegistrationParams")
        with open(self.registrationSaveFile, 'wb') as outfile:
            json.dump(self.registration, outfile)

    def _loadRegistrationParams(self):
        log(">>> _loadRegistrationParams: file: %s" % self.registrationSaveFile)
        if os.path.exists(self.registrationSaveFile):
            with open(self.registrationSaveFile) as infile:
                self.registration = json.load(infile)

    def _login(self):
        """ Login to FreeboxOS using API credentials """
        log(">>> _login")
        if not self.isLoggedIn:
            if not self.isRegistered():
                raise FbxOSException("This app is not registered yet: you have to register it first!")

            # 1st stage: get challenge
            url = self.fbxAddress + "/api/" + self.fbxApiVersion +  "/login/"
            # GET
            log("GET url: %s" % url)
            r = requests.get(url, timeout=3)
            log("GET response: %s" % r.text)
            # ensure status_code is 200, else raise exception
            if requests.codes.ok != r.status_code:
                raise FbxOSException("Get error: %s" % r.text)
            # rc is 200 but did we really succeed?
            resp = json.loads(r.text)
            #log("Obj resp: %s" % resp)
            if resp.get('success'):
                if not resp.get('result').get('logged_in'):
                    self.challenge = resp.get('result').get('challenge')
            else:
                raise FbxOSException("Challenge failure: %s" % resp)

            # 2nd stage: open a session
            global gAppDesc
            apptoken = self.registration.get('app_token')
            key = self.challenge
            log("challenge: " + key + ", apptoken: " + apptoken)
            # Encode to plain string as some python versions seem disturbed else (cf. issue#2)
            if type(key) == unicode:
                key = key.encode()
            # Encode to plain string as some python versions seem disturbed else (cf. issue#3)
            if type(apptoken) == unicode:
                apptoken = apptoken.encode()
            # Hashing token with key
            h = hmac.new(apptoken, key, sha1)
            password = h.hexdigest()
            url = self.fbxAddress + "/api/" + self.fbxApiVersion +  "/login/session/"
            headers = {'Content-type': 'application/json',
                       'charset': 'utf-8', 'Accept': 'text/plain'}
            payload = {'app_id': gAppDesc.get('app_id'), 'password': password}
            #log("Payload: %s" % payload)
            data = json.dumps(payload)
            log("POST url: %s data: %s" % (url, data))
            # post it
            r = requests.post(url, data, headers=headers, timeout=3)
            # ensure status_code is 200, else raise exception
            log("POST response: %s" % r.text)
            if requests.codes.ok != r.status_code:
                raise FbxOSException("Post response error: %s" % r.text)
            # rc is 200 but did we really succeed?
            resp = json.loads(r.text)
            #log("Obj resp: %s" % resp)
            if resp.get('success'):
                self.sessionToken = resp.get('result').get('session_token')
                self.permissions = resp.get('result').get('permissions')
                log("Permissions: %s" % self.permissions)
            else:
                raise FbxOSException("Session failure: %s" % resp)
            self.isLoggedIn = True

    def _logout(self):
        """ logout from FreeboxOS """
        # Not documented yet in the API
        log(">>> _logout")
        if self.isLoggedIn:
            headers = {'X-Fbx-App-Auth': self.sessionToken, 'Accept': 'text/plain'}
            url = self.fbxAddress + "/api/" + self.fbxApiVersion +  "/login/logout/"
            # POST
            log("POST url: %s" % url)
            r = requests.post(url, headers=headers, timeout=3)
            log("POST response: %s" % r.text)
            # ensure status_code is 200, else raise exception
            if requests.codes.ok != r.status_code:
                raise FbxOSException("Post error: %s" % r.text)
            # rc is 200 but did we really succeed?
            resp = json.loads(r.text)
            #log("Obj resp: %s" % resp)
            if not resp.get('success'):
                raise FbxOSException("Logout failure: %s" % resp)
        self.isLoggedIn = False

    def hasRegistrationParams(self):
        """ Indicate whether registration params look initialized """
        log(">>> hasRegistrationParams")
        if None != self.registration.get('track_id') and '' != self.registration.get('app_token'):
            return True
        else:
            self._loadRegistrationParams()
            return None != self.registration.get('track_id') and '' != self.registration.get('app_token')

    def getRegistrationStatus(self):
        """ Get the current registration status thanks to the track_id """
        log(">>> getRegistrationStatus")
        if self.hasRegistrationParams():
            url = self.fbxAddress + \
                "/api/" + self.fbxApiVersion +  "/login/authorize/%s" % self.registration.get('track_id')
            log(url)
            # GET
            log("GET url: %s" % url)
            r = requests.get(url, timeout=3)
            log("GET response: %s" % r.text)
            # ensure status_code is 200, else raise exception
            if requests.codes.ok != r.status_code:
                raise FbxOSException("Get error: %s" % r.text)
            resp = json.loads(r.text)
            return resp.get('result').get('status')
        else:
            return "Not registered yet!"

    def isRegistered(self):
        """ Check that the app is currently registered (granted) """
        log(">>> isRegistered")
        if self.hasRegistrationParams():
            # Incompatibility with external IP
            # and 'granted' == self.getRegistrationStatus():
            return True
        else:
            return False

    def registerApp(self):
        """ Register this app to FreeboxOS to that user grants this apps via Freebox Server
LCD screen. This command shall be executed only once. """
        log(">>> registerApp")
        register = True
        if self.hasRegistrationParams():
            status = self.getRegistrationStatus()
            if 'granted' == status:
                print "This app is already granted on Freebox Server (app_id = %s). You can now dialog with it." % self.registration.get('track_id')
                register = False
            elif 'pending' == status:
                print "This app grant is still pending: user should grant it on Freebox Server lcd/touchpad (app_id = %s)." % self.registration.get('track_id')
                register = False
            elif 'unknown' == status:
                print "This app_id (%s) is unknown by Freebox Server: you have to register again to Freebox Server to get a new app_id." % self.registration.get('track_id')
            elif 'denied' == status:
                print "This app has been denied by user on Freebox Server (app_id = %s)." % self.registration.get('track_id')
                register = False
            elif 'timeout' == status:
                print "Timeout occured for this app_id: you have to register again to Freebox Server to get a new app_id (current app_id = %s)." % self.registration.get('track_id')
            else:
                print "Unexpected response: %s" % status

        if register:
            global gAppDesc
            url = self.fbxAddress + "/api/" + self.fbxApiVersion +  "/login/authorize/"
            data = json.dumps(gAppDesc)
            headers = {
                'Content-type': 'application/json', 'Accept': 'text/plain'}
            # post it
            log("POST url: %s data: %s" % (url, data))
            r = requests.post(url, data=data, headers=headers, timeout=3)
            log("POST response: %s" % r.text)
            # ensure status_code is 200, else raise exception
            if requests.codes.ok != r.status_code:
                raise FbxOSException("Post error: %s" % r.text)
            # rc is 200 but did we really succeed?
            resp = json.loads(r.text)
            #log("Obj resp: %s" % resp)
            if True == resp.get('success'):
                self.registration['app_token'] = resp.get('result').get('app_token')
                self.registration['track_id'] = resp.get('result').get('track_id')
                self._saveRegistrationParams()
                print "Now you have to accept this app on your Freebox server: take a look on its lcd screen."
            else:
                print "NOK"

    def testFonction(self):
        print("test function")
        return True

    def extractFilenameFromFilePath(self,value):
        """ Extract filename from filepath """
        log(">>> extractFilenameFromFilePath")
        head, tail = os.path.split(value)
        log("head %s, tail %s" % (head,tail))
        # Add date/time option
        if True == self.addDateTimeToFile:
            today = datetime.date.today()
            tail = '%s.%s.%s' % (tail, today.strftime('%Y%m%d'), time.strftime('%H%M%S'))
        return tail

    def uploadFile(self, values):
        log(">>> uploadFile")
        self._login()
        headers = {'X-Fbx-App-Auth': self.sessionToken, 'Accept': 'text/plain'}
        encoded = base64.b64encode(self.targetFoldername)

        # For each file giving in argument
        # TODO logout call missing when local file doesn't exists.
        for filepath in values:
            log ("filepath: %s" % filepath)
            filename = self.extractFilenameFromFilePath(filepath)
            data = {'dirname': encoded, 'upload_name': filename}
            url = self.fbxAddress + "/api/" + self.fbxApiVersion +  "/upload/"
            log("POST url: %s data: %s" % (url, json.dumps(data)))
            r = requests.post(url, data=json.dumps(data), headers=headers, timeout=1)
            log("POST response: %s" % r.text)
            # ensure status_code is 200, else raise exception
            if requests.codes.ok != r.status_code:
                raise FbxOSException("Get error: %s" % r.text)
            # rc is 200 but did we really succeed?
            resp = json.loads(r.text)
            if True == resp.get('success'):
                id_auth=resp.get('result').get('id')
                log("Id authorization: %s" % id_auth)
                url = self.fbxAddress + "/api/" + self.fbxApiVersion +  "/upload/%s/send" % id_auth
                files = {'file': (filename, open(filepath, 'rb'), 'multipart/form-data', {'Expires': '0'})}
                r = requests.post(url, files=files)
                log("POST response: %s" % r.text)
                if requests.codes.ok != r.status_code:
                    raise FbxOSException("Get error: %s" % r.text)
                resp = json.loads(r.text)
                print("Upload of %s in %s completed" % (filename , self.targetFoldername))
            elif resp.get('error_code') == 'conflict':
                raise FbxOSException("File %s already exist in %s" % (filename , self.targetFoldername))
            else:
                raise FbxOSException("Upload authorization failure: %s" % resp)

        self._logout()
        return True

class FreeboxOSCli:

    """ Command line (cli) interpreter and dispatch commands to controller """

    def __init__(self, controller):
        """ Constructor """
        self.controller = controller
        # Configure parser
        self.parser = argparse.ArgumentParser(
            description='Command line utility to upload files to freebox.')
        # CLI related actions
        self.parser.add_argument(
            '--version', action='version', version="%(prog)s " + __version__)
        self.parser.add_argument(
            '-v', action='store_true', help='verbose mode')
        self.parser.add_argument(
            '-c', nargs=1, help='configuration file to store/retrieve FreeboxOS registration parameters')
        self.parser.add_argument(
            '-d', action='store_true', help='Add date and time extension to each file')
        # Real freeboxOS actions
        group = self.parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--regapp', default=argparse.SUPPRESS, action='store_true',
            help='register this app to FreeboxOS and save result in configuration file (to be executed only once)')
        group.add_argument(
            '--uploadfile', help='upload a file to freebox server', nargs='+')
        group.add_argument(
            '--testfonction', default=argparse.SUPPRESS, action='store_true',
            help='just for test')
        # Configure cmd=>callback association
        self.cmdCallbacks = {
            'regapp': self.controller.registerApp,
            'uploadfile': self.controller.uploadFile,
            'testfonction': self.controller.testFonction
        }
        self.rc = False
        #atexit.register(cleanup, self.rc)

    def cmdExec(self, argv):
        """ Parse the parameters and execute the associated command """
        log ("argv %s" % argv)
        args = self.parser.parse_args(argv)
        log ("args %s" % args)
        argsdict = vars(args)
        # Activate verbose mode if requested
        if True == argsdict.get('v'):
            global gVerbose
            gVerbose = True
        #log("Args dict: %s" % argsdict)
        if argsdict.get('c'):
            self.controller.registrationSaveFile = argsdict.get('c')[0]
        if argsdict.get('d'):
            self.controller.addDateTimeToFile = True
        # Suppress -v, -d, -c commands
        del argsdict['v']
        del argsdict['c']
        del argsdict['d']

        # Weird ! Need to be corrected.
        if not argsdict.get('uploadfile'):
              del argsdict['uploadfile']

        # Let's execute FreeboxOS cmd
        return self.dispatch(argsdict.keys(), argsdict.values())

    def dispatch(self, args, values):
        """ Call controller action """
        for cmd in args:
            # retrieve callback associated to cmd and execute it, if not found
            # display help
            if 'uploadfile' == cmd:
                # ??? why two dimensionals table
                return self.cmdCallbacks.get(cmd, self.parser.print_help)(values[0])
            else:
                return self.cmdCallbacks.get(cmd, self.parser.print_help)()

if __name__ == '__main__':
        controller = FreeboxOSCtrl()
        cli = FreeboxOSCli(controller)
        controller.rc = cli.cmdExec(sys.argv[1:])
        sys.exit(controller.rc)
