#!/usr/bin/python3
#v0.20200407

import requests
import sys, getopt
import logging
import urllib3
import urllib
import os
import time
import datetime
import traceback
import math
import configparser
import copy
from retry import retry
from retry.api import retry_call
from requests_toolbelt import (MultipartEncoder,
                               MultipartEncoderMonitor)


#temp
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
clear = lambda: os.system('clear')


class Tools(object):
    @staticmethod
    def sizeof_fmt(num, suffix='B'):
        #print(type(num))
        if type(num) == int:
            #['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
            for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
                if abs(num) < 1024.0:
                    return "%3.1f%s%s" % (num, unit, suffix)
                num /= 1024.0
            return "%.1f%s%s" % (num, 'Y', suffix)
        return ""


class ThunderDriveAPI(object):
    """thunderdrive.io api beta"""
    URL = "https://app.thunderdrive.io/secure/"

    errorStr = 'Whoops, looks like something went wrong.'

    #tmp
    ssl_verify = False
    #proxies = {"https": "https://192.168.10.4:58080", "http": "http://192.168.10.4:58080"}
    proxies = None

    headers = dict()
    headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0'
    headers['Accept'] = "application/json, text/plain, */*"
    headers['Accept-Encoding'] = "gzip, deflate, br"
    headers['Accept-Lenguage'] = "en-US,en;q=0.5"

    logger = logging.getLogger(__name__)

    progressBarLen = 30

    def __init__(self, usr, psw, logger=None, https=None, http=None):
        if logger != None:
            self.setLogger(logger)
        self.session = requests.Session()

        self.setProxy(https=https, http=http)

        self._login(usr, psw)

        self.userName = usr

        self.getFolders()  #root folder
        #get user ID
        self.userID = self.getUserID()
        self.getAllFolders()

    def _login(self, usr, psw):
        data = {"email":usr, "password":psw}
        loginResp = self.post(self.URL + "auth/login", data, testResp=True)
        if loginResp["status"] == "success":
            self.loggedin = True

    def setLogger(self, logger):
        self.logger = logger

    def setProxy(self, https=None, http=None):
        self.proxies = {}
        if https != None:
            self.proxies["https"] = https
        if http != None:
            self.proxies["http"] = http
        if len(self.proxies) == 0:
            self.proxies = None
        else:
            self.logger.info("proxy enabled")

    def get(self, _url, stream=None, params=None, testResp=False, convertToJSON=True):
        resp = self.session.get(_url, proxies=self.proxies, verify=self.ssl_verify, stream=stream, headers=self.headers, params=params)
        resp.raise_for_status()

        if testResp:
            if (str(resp.content)).find(self.errorStr) > 0:
                raise Exception("wyx: " + self.errorStr)

        if convertToJSON:
            return resp.json()
        else: 
            return resp

    def post(self, _url, _data, testResp=False, headers=headers, auth=None, convertToJSON=True):

        resp = self.session.post(_url, data=_data
                                    , proxies=self.proxies, verify=self.ssl_verify
                                    , headers=headers, auth=auth
                                )
        resp.raise_for_status()

        if testResp:
            if (str(resp.content)).find(self.errorStr) > 0:
                raise Exception("wyx: " + self.errorStr)
        if convertToJSON:
            return resp.json()
        else:
            return resp

    def getFolders(self, folderHash = ""):
        #getFolderItems
        params = None
        if folderHash != "":
            params = [('orderBy', 'name'), ('orderDir', ''), ('folderId', folderHash)]
        self.lastResp = self.get(self.URL + "drive/entries", params=params)

    def getUserID(self):
        return self.lastResp["data"][0]["users"][0]["id"]

    def getAllFolders(self):
        self.allFolders = self.get(self.URL + "drive/users/{}/folders".format(self.userID))["folders"]
        return self.allFolders

    def getSpaceUsage(self):
        resp = self.get(self.URL + "drive/user/space-usage")
        return resp["used"], resp["available"]

    def _printProgressBar (self, iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█', printEnd="\r"):
        """
        Call in a loop to create terminal progress bar
        @params:
            iteration   - Required  : current iteration (Int)
            total       - Required  : total iterations (Int)
            prefix      - Optional  : prefix string (Str)
            suffix      - Optional  : suffix string (Str)
            decimals    - Optional  : positive number of decimals in percent complete (Int)
            length      - Optional  : character length of bar (Int)
            fill        - Optional  : bar fill character (Str)
            printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
        """
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)

        print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = printEnd)
        
        # # Print New Line on Complete
        # if iteration == total: 
        #     print()

    __prevTime = None
    __prevChunk = None
    def _getUpDownSpeed(self, chC = 0, init = False):
        speed = None
        
        if self.__prevChunk == None or init:
            self.__prevChunk = chC
        if self.__prevTime == None or init:
            self.__prevTime = time.time()

        dTime = round(float(time.time() - self.__prevTime), 3)
        dChunk = chC - self.__prevChunk

        if dTime != 0:
            speed = int(dChunk / dTime)

        self.__prevTime = time.time()
        self.__prevChunk = chC

        retSpeed = Tools.sizeof_fmt(speed) + " " * 10

        return retSpeed[0:7]
        #return str(speed)
        # + " " + str(chC)

    def downloadFileWithRetry(self, fileInfo):
        retry_call(self.downloadFile, fargs=[fileInfo], tries=3, delay=5, backoff=2, max_delay=30, logger=self.logger)

    def findFolderID(self, tdir):
        for folder in self.allFolders:
            if folder["name"].upper() == tdir.upper():
                self.logger.info("Found dir '{}': id - {}; hash - {}".format(tdir, folder["id"], folder["hash"]))
                return str(folder["id"]), folder["hash"]

        self.logger.info("Directory '{}' not found in ThunderDrive.io".format(tdir))
        return "", ""

    def uploadFileWithRetry(self, filePaths, folderID = "", folderHash = ""):
        for filePath in filePaths:
            retry_call(self.uploadFile, fargs=[filePath], fkwargs={"folderID": folderID, "folderHash": folderHash}
                        , tries=3, delay=5, backoff=2, max_delay=30, logger=self.logger)

    __upload_step = 0
    def __upload_callback(self, encoder):
        """Upload progress bar."""
        self.__upload_step +=1
        #if upload_step % 200 != 0 and abs(encoder.bytes_read - encoder.len) > 100:
        if self.__upload_step % 200 != 0:
            return

        fraction = encoder.bytes_read / encoder.len * 100
        speed = self._getUpDownSpeed(encoder.bytes_read)
        self._printProgressBar(fraction, 100.01, length = self.progressBarLen, prefix = 'P: ', suffix=speed)

    def __rewrite_request(self, prepared_request):
        return prepared_request

    def uploadFile(self, filePath, folderID = "", folderHash = ""
        ):

        #TODO
        headersupl = dict()
        headersupl = copy.deepcopy(self.headers)
        #headersupl['Referer'] = 'https://app.thunderdrive.io/drive/folders/' + folderHash
        headersupl['X-XSRF-TOKEN'] = urllib.parse.unquote(self.session.cookies["XSRF-TOKEN"]) #?????
        #headersupl['Origin'] = "https://app.thunderdrive.io"

        with open(filePath, 'rb') as f:
            form = MultipartEncoder({
                'parentId': (None, folderID),
                'file': (filePath, f),
            })
            monitor = MultipartEncoderMonitor(form, callback=self.__upload_callback)
            headersupl["Content-Type"] = monitor.content_type
            
            #self.logger.info(filePath + ": uploading ....")
            self.logger.info("B: uploading file '{}' {}".format(filePath, datetime.datetime.now().strftime('%H:%M:%S')) )

            self._printProgressBar(0, 100, length = self.progressBarLen, prefix = 'P: ')
            self._getUpDownSpeed(init=True)

            #r = 
            self.post(self.URL + "uploads", monitor, headers=headersupl
                #, auth=self.__rewrite_request
                , convertToJSON = False
                )
            self._printProgressBar(100, 100, length = self.progressBarLen, prefix = 'P: ', suffix="        ")
            print()
        
        #print()
        #self.logger.info(r)
        #r.raise_for_status()
        self.logger.info("E: uploading done '{}' {}".format(filePath, datetime.datetime.now().strftime('%H:%M:%S')) )
        #self.logger.info("done")

    def downloadFile(self, fileInfo):

        fileSize = int(fileInfo["file_size"])
        fName = fileInfo["name"]

        self.logger.info("B: " + fName + " " + datetime.datetime.now().strftime('%H:%M:%S') + " (" + Tools.sizeof_fmt(fileSize) + ")" )

        r = self.get(self.URL + "uploads/download", params=[('hashes',fileInfo["hash"])], convertToJSON = False, stream=True)

        self.logger.info("D: " + fName + " " + datetime.datetime.now().strftime('%H:%M:%S'))
        self._printProgressBar(0, 100, length = self.progressBarLen, prefix = 'P: ')
        i = 0
        chC = 0
        chunk_size = 1024 * 512
        self._getUpDownSpeed(init=True)
        with open(fName, 'wb') as f:
            for ch in r.iter_content(chunk_size = chunk_size):
                f.write(ch)
                i += 1
                chC += chunk_size
                if i % 5 == 0:
                    #print (i, chC / fileSize * 100)
                    speed = self._getUpDownSpeed(chC)
                    self._printProgressBar(chC / fileSize * 100, 100, length = self.progressBarLen, prefix = 'P: ', suffix=speed)

                #time.sleep(0.1)
            self._printProgressBar(100, 100, length = self.progressBarLen, prefix = 'P: ', suffix="        ")
            print()

        r.close()
        r.raise_for_status()
        self.logger.info("E: " + fName + " " + datetime.datetime.now().strftime('%H:%M:%S'))
        #pass

    def getSearchRez(self, query):
        self.logger.info("searching ({}) .....".format(query))
        params = [('orderBy','name'), ('orderDir',''), ('type',''), ('query', query)]
        #self.logger.info("pr")
        resp = self.get(self.URL + "drive/entries", params=params)
        #self.logger.info("pb")
        self.lastResp = resp
        return resp

    def downloadAllSearchresults(self, filesInfo):
        urls_to_download = filesInfo["data"]
        sk = 0
        for url in urls_to_download:
            sk += 1
            self.logger.info(str(sk) + "/" + str(len(urls_to_download)))
            if url["type"] == "folder":
                self.logger.info("skipping folder: " + url["name"])
            else:
                try:
                    self.downloadFileWithRetry(url)
                except Exception as ex:
                    self.logger.exception(ex)


class InteractiveMode(object):
    
    def __init__(self, thunderClient):
        self.thunderClient = thunderClient
        self.interactiveMode()

    def printMenu(self, thunderClient, folderSelected, currentFolder, stackHash):
        if thunderClient.loggedin:
            if folderSelected:
                print("folder selected: ", currentFolder)
            else:
                print("file selected: ", currentFolder)

            print("s - search")
        # if not loggedin:
        #     print("l - login")
        if stackHash.__len__() > 0:
            print ("u - UP")
        print("q - quit")

    @staticmethod
    def printItems(_data, currentItemList = {}, userName = ""):
        i = 0
        #d = _data.json()
        d = _data
        currentItemList.clear()
        total = 0
        for key in d["data"]:
            i += 1
            currentItemList[str(i)] = key
            user = ""
            try:
                user_array = key["users"]
                if len(user_array) > 0:
                    user = user_array[0]["email"]
                if userName == user:
                    user = ""
            except:
                pass
            print(i, key["name"], "(", key["type"], Tools.sizeof_fmt(key["file_size"]),")", user)
            #, key["id"], key["path"], key["type"], key["hash"]
            if type(key["file_size"]) == int:
                total += key["file_size"]
        if total > 0 : 
            print ("Toltal:", Tools.sizeof_fmt(total))

    def printFileMenu(self, ):
        print("i - info")
        print("D - download")

    def fileInfoPrint(self, _data):
        print("name: ", _data["name"])
        print("file_size: ", Tools.sizeof_fmt(int(_data["file_size"])))
        print("hash: ", _data["hash"])
        print(_data)
        input("press any key to continue")

    def interactiveMode(self):

        folderSelected = True
        currentFolder = "root"
        #prevFolder = ""

        currentHash = "root"
        #prevHash = ""

        stackHash = []#deque()
        stackNames = []#deque()

        currentItemList = {}
        fileInfo = None


        while True:
            # global folderSelected
            # global currentHash
            # global currentFolder
            # global fileInfo
            clear()
            #print(stackHash)
            self.printMenu(self.thunderClient, folderSelected, currentFolder, stackHash)
            if self.thunderClient.loggedin:
                if folderSelected:
                    self.printItems(self.thunderClient.lastResp, currentItemList, self.thunderClient.userName)
                else:
                    self.printFileMenu()    ##folder meniu

            cmd = input("cmd: ")

            if cmd == "q":
                sys.exit(0)
            elif cmd == "i":
                self.fileInfoPrint(fileInfo)
            elif cmd == "D":
                self.thunderClient.downloadFileWithRetry(fileInfo)
            # elif cmd == "U":
            #     uploadFile()
            # elif cmd == "l":
            #     if not loggedin:
            #         doLogin()
            #     getFolders("root")
            elif cmd == "SDA":
                self.thunderClient.downloadAllSearchresults(self.thunderClient.lastResp)
            elif cmd == "s":
                q = input("query: ")
                self.thunderClient.getSearchRez(q)
                stackHash.append(currentHash)
                stackNames.append(currentFolder)
                # currentHash = q
                # #prevFolder = currentFolder
                # currentFolder = rr["name"]            
            elif cmd == "u":
                currentHash = stackHash.pop()
                self.thunderClient.getFolders(currentHash)
                currentFolder = stackNames.pop()
                folderSelected = True
            else:
                rr = currentItemList.get(cmd, None)
                if rr == None:
                    print("?????")
                else:
                    if rr["type"] == "folder":
                        self.thunderClient.getFolders(rr["hash"])
                        folderSelected = True
                        fileInfo = None
                    else:
                        folderSelected = False
                        fileInfo = rr

                    stackHash.append(currentHash)
                    stackNames.append(currentFolder)
                    #prevHash = currentHash
                    currentHash = rr["hash"]
                    #prevFolder = currentFolder
                    currentFolder = rr["name"]


def paramModeHelp():
    #print("help")
    print("--search= - phrase to search")
    print("--list - list founded files")
    print("--prompt - stops before download")
    print("--uploadfile=file.txt")
    print("--uploadmode - example: thunderdrive.py --uploadmode file1 file2 ...")
    print("--downloadmode - example: thunderdrive.py --downloadmode file1 file2 ...")
    print("--targetdir=THdir - target directory in thinderdrive.io for upload") 

def paramMode(argv_full, logger):
    #print(argv_full)
    argv = argv_full[1:]
    #print(argv)
    
    searchPhrases = []
    useproxy = False
    listfiles = False
    prompt = False
    upload = False
    download = False
    interactive = False
    #filename = ""
    filenames = []
    tdirectory = None

    try:
        #opts, args = getopt.getopt \
        opts, args = getopt.getopt \
            (argv, "h", ["search=", "useproxy", "list", "prompt", "help", "interactive", "uploadmode", "downloadmode", "uploadfile=", "targetdir="])
    except getopt.GetoptError  as err:
        print(err)
        sys.exit(2)
    #print(opts, args)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            paramModeHelp()
            sys.exit(0)
        elif opt == "--downloadmode":
            download = True
            searchPhrases = args
            #TODO: pabaigti
        elif opt == "--search":
            download = True
            searchPhrases.append(arg)
        # elif opt in ("--disableproxy"):
        #     disableproxy = True
        elif opt in ("--list"):
            listfiles = True
        elif opt in ("--prompt"):
            prompt = True
            listfiles = True
        elif opt == "--uploadmode":
            upload = True
            filenames = args
        elif opt == "--uploadfile":
            upload = True
            filenames.append(arg)
        elif opt in ("--tdir", "--targetdir"):
            tdirectory = arg
        elif opt in ("--interactive"):
            interactive = True
        elif opt in ("--useproxy"):
            useproxy = True

    https = http = None
    if useproxy:
        https = "https://192.168.10.4:58080"
        http = "http://192.168.10.4:58080"

    usr, psw = getLoginInfo()
    thunderClient = ThunderDriveAPI(usr, psw, logger, https=https, http=http)

    if interactive:
        InteractiveMode(thunderClient)
        sys.exit(0)

    if upload:
        folderID = folderHash = ""
        if tdirectory != None:
            folderID, folderHash = thunderClient.findFolderID(tdirectory)
        thunderClient.uploadFileWithRetry(filenames, folderID, folderHash)
        sys.exit(0)

    if download:
        for searchPhrase in searchPhrases:
            thunderClient.getSearchRez(searchPhrase)
            if listfiles:
                InteractiveMode.printItems(_data = thunderClient.lastResp, userName=thunderClient.userName)
            if prompt:
                input("press any key to continue download; ctrl+C - to stop")
            thunderClient.downloadAllSearchresults(thunderClient.lastResp)
        logger.info("All files downloaded")
        sys.exit(0)

def getLoginInfo():
    usr = None
    psw = None
    usrDir = os.path.expanduser("~")
    config = configparser.ConfigParser()
    if os.path.exists("./config.txt"):
        config.read("./config.txt")
    elif os.path.exists(usrDir + "/config.txt"):
        config.read(usrDir + "/config.txt")
    else:
        raise FileExistsError('Nerastas failas')
    usr = config.get("thunderdrive","username")
    psw = config.get("thunderdrive","password")
    return usr, psw

def prepLogger():
    handlers = []
    # file_handler = logging.FileHandler(filename='/tmp/thunderdrive.log')
    # handlers.append(file_handler)
    stdout_handler = logging.StreamHandler(sys.stdout)
    handlers.append(stdout_handler)

    if len(handlers) == 0:
        return None

    logging.basicConfig(
        level=logging.INFO,
        #level=logging.DEBUG,
        format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
        handlers=handlers
    )

    stdout_handler.setFormatter(logging.Formatter('%(message)s'))
    logger = logging.getLogger()
    return logger


if __name__ == "__main__": 
    logger = prepLogger()
    try:
        if len(sys.argv) > 1:
            paramMode(sys.argv, logger)
        else:
            paramModeHelp()
    except KeyboardInterrupt:
        print()
        sys.exit(0)
    except Exception as ex:
        #print(ex)
        if logger != None:
            logger.exception()
        else:
            print(ex)
        sys.exit(1)
    finally:
        pass

sys.exit(0)

