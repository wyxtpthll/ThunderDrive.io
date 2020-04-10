#!/usr/bin/python3
# v0.20200407

import requests
import sys
import getopt
import logging
import urllib
import os
import time
import datetime
import configparser
import copy
from retry.api import retry_call
from requests_toolbelt import (MultipartEncoder,
                               MultipartEncoderMonitor)
# import urllib3
# import traceback
# import math
# from retry import retry


# # temp
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def clear():
    # clear = lambda: os.system('clear')
    return os.system('clear')


class Tools(object):
    @staticmethod
    def sizeof_fmt(num, suffix='B'):
        # print(type(num))
        if type(num) == int:
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

    # temp
    # ssl_verify = False
    ssl_verify = True
    proxies = None

    headers = dict()
    headers['User-Agent'] =\
        'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0'
    headers['Accept'] = "application/json, text/plain, */*"
    headers['Accept-Encoding'] = "gzip, deflate, br"
    headers['Accept-Lenguage'] = "en-US,en;q=0.5"

    logger = logging.getLogger(__name__)

    progress_bar_len = 30
    tries = 3

    def __init__(self, usr, psw, logger=None,
                 https_proxy=None, http_proxy=None,
                 ssl_verify=True):

        if logger is not None:
            self.set_logger(logger)
        self.session = requests.Session()

        self.set_proxy(https=https_proxy, http=http_proxy)
        self.ssl_verify = ssl_verify

        self._login(usr, psw)

        self.user_name = usr

        self.get_folders()  # root folder
        # get user ID
        self.userID = self.get_user_id()
        self.get_all_folders()

    def _login(self, usr, psw):
        data = {"email": usr, "password": psw}
        login_resp = self.post(self.URL + "auth/login", data, test_resp=True)
        if login_resp["status"] == "success":
            self.logged_in = True

    def set_logger(self, logger):
        self.logger = logger

    def set_proxy(self, https=None, http=None):
        self.proxies = {}
        if https is not None:
            self.proxies["https"] = https
        if http is not None:
            self.proxies["http"] = http
        if len(self.proxies) == 0:
            self.proxies = None
        else:
            self.logger.info("proxy enabled")

    def get(self, _url, stream=None, params=None, test_resp=False,
            convert_to_json=True):

        resp = self.session.get(_url, proxies=self.proxies,
                                verify=self.ssl_verify, stream=stream,
                                headers=self.headers, params=params)
        resp.raise_for_status()

        if test_resp:
            if (str(resp.content)).find(self.errorStr) > 0:
                # raise Exception("wyx: " + self.errorStr)
                raise Exception(self.errorStr)

        if convert_to_json:
            return resp.json()
        else:
            return resp

    def post(self, _url, _data, test_resp=False,
             headers=headers, auth=None, convert_to_json=True):

        resp = self.session.post(_url, data=_data, proxies=self.proxies,
                                 verify=self.ssl_verify,
                                 headers=headers, auth=auth)
        resp.raise_for_status()
        # print(resp.text)

        if test_resp:
            if (str(resp.content)).find(self.errorStr) > 0:
                # raise Exception("wyx: " + self.errorStr)
                raise Exception(self.errorStr)
        if convert_to_json:
            return resp.json()
        else:
            return resp

    def get_folders(self, folder_hash=""):
        params = None
        if folder_hash != "":
            params = [('orderBy', 'name'),
                      ('orderDir', ''),
                      ('folderId', folder_hash)]
        self.last_resp = self.get(self.URL + "drive/entries", params=params)

    def get_user_id(self):
        return self.last_resp["data"][0]["users"][0]["id"]

    def get_all_folders(self):
        self.allFolders = self.get(self.URL + "drive/users/{}/folders".
                                   format(self.userID))["folders"]
        return self.allFolders

    def get_space_usage(self):
        resp = self.get(self.URL + "drive/user/space-usage")
        return resp["used"], resp["available"]

    def _print_progress_bar(self, iteration, total, prefix='', suffix='',
                            decimals=1, length=100, fill='█', printEnd="\r"):
        """
        Call in a loop to create terminal progress bar
        @params:
            iteration - Req.: current iteration (Int)
            total     - Req.: total iterations (Int)
            prefix    - Opt.: prefix string (Str)
            suffix    - Opt.: suffix string (Str)
            decimals  - Opt.: posit. num. of decimals in percent complete (Int)
            length    - Opt.: character length of bar (Int)
            fill      - Opt.: bar fill character (Str)
            printEnd  - Opt.: end character (e.g. "\r", "\r\n") (Str)
        """

        percent = ("{0:." + str(decimals) + "f}").\
            format(100 * (iteration / float(total)))
        filled_length = int(length * iteration // total)
        bar = fill * filled_length + '-' * (length - filled_length)

        print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix),
              end=printEnd)
        # # Print New Line on Complete
        # if iteration == total:
        #     print()

    __prevTime = None
    __prevChunk = None
    __beg_time = None

    def _get_up_down_speed(self, chC=0, total=None, init=False):
        speed = None

        if self.__prevChunk is None or init:
            self.__prevChunk = chC
        if self.__prevTime is None or init:
            self.__prevTime = time.time()
        if self.__beg_time is None or init:
            self.__beg_time = datetime.datetime.now()

        dTime = round(float(time.time() - self.__prevTime), 3)
        dChunk = chC - self.__prevChunk

        if dTime != 0:
            speed = int(dChunk / dTime)

        ttl_str = ""
        if total is not None and self.__beg_time is not None:
            seconds = (datetime.datetime.now() - self.__beg_time).\
                total_seconds()
            ttl = seconds / chC * (total - chC)
            if (ttl / 60 > 99):
                ttl_str = " " + str(round(ttl / 60, 0)) + "m"
            elif (ttl / 60 > 10):
                ttl_str = " " + str(round(ttl / 60, 1)) + "m"
            else:
                ttl_str = " " + "{:.0f}".format(round(ttl, 0)) + "s"
            # ttl_str = " " + str(ttl)
            # ttl_str = '{} {} {}'.format(seconds, chC, total)
            # print('{} {} {} {}'.format(seconds, chC, total, round(ttl, 2)))

        self.__prevTime = time.time()
        self.__prevChunk = chC

        retSpeed = Tools.sizeof_fmt(speed) + ttl_str + " " * 10
        return retSpeed[0:7 + 6]

    def download_file_with_retry(self, file_info):
        retry_call(self.download_file, fargs=[file_info], tries=self.tries,
                   delay=5, backoff=2, max_delay=30, logger=self.logger)

    def find_folder_id(self, tdir):
        for folder in self.allFolders:
            if folder["name"].upper() == tdir.upper():
                self.logger.info("Found dir '{}': id - {}; hash - {}".
                                 format(tdir, folder["id"], folder["hash"]))
                return str(folder["id"]), folder["hash"]

        self.logger.info("Directory '{}' not found in ThunderDrive.io".
                         format(tdir))
        return "", ""

    def upload_file_with_retry(self, file_paths, folder_id="", folder_hash=""):
        for filePath in file_paths:
            retry_call(self.upload_file, fargs=[filePath],
                       fkwargs={"folder_id": folder_id,
                       "folder_hash": folder_hash}, tries=self.tries,
                       delay=5, backoff=2, max_delay=30, logger=self.logger)

    __upload_step = 0

    def __upload_callback(self, encoder):
        """Upload progress bar."""
        self.__upload_step += 1
        if self.__upload_step % 200 != 0:
            return

        fraction = encoder.bytes_read / encoder.len * 100
        speed = self._get_up_down_speed(chC=encoder.bytes_read,
                                        total=encoder.len)
        self._print_progress_bar(fraction, 100.01,
                                 length=self.progress_bar_len, prefix='P: ',
                                 suffix=speed)

    def __rewrite_request(self, prepared_request):
        return prepared_request

    def upload_file(self, filePath, folder_id="", folder_hash=""):
        headersupl = dict()
        headersupl = copy.deepcopy(self.headers)
        headersupl['X-XSRF-TOKEN'] =\
            urllib.parse.unquote(self.session.cookies["XSRF-TOKEN"])
        # headersupl['Origin'] = "https://app.thunderdrive.io"

        with open(filePath, 'rb') as f:
            form = MultipartEncoder({
                'parentId': (None, folder_id),
                'file': (filePath, f),
            })
            monitor =\
                MultipartEncoderMonitor(form, callback=self.__upload_callback)
            headersupl["Content-Type"] = monitor.content_type

            # self.logger.info(filePath + ": uploading ....")
            self.logger.info("B: uploading file '{}' {}".
                             format(filePath,
                                    datetime.datetime.now().
                                    strftime('%H:%M:%S')))

            self._print_progress_bar(0, 100, length=self.progress_bar_len,
                                     prefix='P: ')
            self._get_up_down_speed(init=True)

            # r =
            # self.post(self.URL + "uploads", monitor, headers=headersupl,
            #   auth=self.__rewrite_request, convert_to_json=False)
            self.post(self.URL + "uploads", monitor, headers=headersupl,
                      convert_to_json=False)
            self._print_progress_bar(100, 100, length=self.progress_bar_len,
                                     prefix='P: ', suffix=" " * 13)
            print()

        # print()
        # self.logger.info(r)
        # r.raise_for_status()
        self.logger.info("E: uploading done '{}' {}".
                         format(filePath, datetime.datetime.now().
                                strftime('%H:%M:%S')))
        # self.logger.info("done")

    def download_file(self, file_info):

        file_size = int(file_info["file_size"])
        file_name = file_info["name"]

        self.logger.info("B: " + file_name + " "
                         + datetime.datetime.now().strftime('%H:%M:%S') + " ("
                         + Tools.sizeof_fmt(file_size) + ")")

        r = self.get(self.URL + "uploads/download",
                     params=[('hashes', file_info["hash"])],
                     convert_to_json=False, stream=True)

        self.logger.info("D: " + file_name + " " + datetime.datetime.now().
                         strftime('%H:%M:%S'))
        self._print_progress_bar(0, 100, length=self.progress_bar_len,
                                 prefix='P: ')
        i = 0
        chC = 0
        chunk_size = 1024 * 512
        self._get_up_down_speed(init=True)
        with open(file_name, 'wb') as f:
            for ch in r.iter_content(chunk_size=chunk_size):
                f.write(ch)
                i += 1
                chC += chunk_size
                if i % 5 == 0:
                    # print (i, chC / file_size * 100)
                    speed = self._get_up_down_speed(chC=chC, total=file_size)
                    self._print_progress_bar(chC / file_size * 100, 100,
                                             length=self.progress_bar_len,
                                             prefix='P: ', suffix=speed)

                # time.sleep(0.1)
            self._print_progress_bar(100, 100, length=self.progress_bar_len,
                                     prefix='P: ', suffix=" " * 13)
            print()

        r.close()
        r.raise_for_status()
        self.logger.info("E: " + file_name + " " + datetime.datetime.now().
                         strftime('%H:%M:%S'))

    def get_search_rez(self, query):
        self.logger.info("searching ({}) .....".format(query))
        params = [('orderBy', 'name'), ('orderDir', ''),
                  ('type', ''), ('query', query)]
        resp = self.get(self.URL + "drive/entries", params=params)
        self.last_resp = resp
        return resp

    def download_all_search_results(self, filesInfo):
        urls_to_download = filesInfo["data"]
        sk = 0
        for url in urls_to_download:
            sk += 1
            self.logger.info(str(sk) + "/" + str(len(urls_to_download)))
            if url["type"] == "folder":
                self.logger.info("skipping folder: " + url["name"])
            else:
                try:
                    self.download_file_with_retry(url)
                except Exception as ex:
                    self.logger.exception(ex)


class InteractiveMode(object):

    def __init__(self, thunder_client):
        self.thunder_client = thunder_client
        self.interactiveMode()

    def print_menu(self, thunder_client, folder_selected,
                   current_folder, stack_hash):
        if thunder_client.logged_in:
            if folder_selected:
                print("folder selected: ", current_folder)
            else:
                print("file selected: ", current_folder)

            print("s - search")
        # if not logged_in:
        #     print("l - login")
        if stack_hash.__len__() > 0:
            print("u - UP")
        print("q - quit")

    @staticmethod
    def print_items(_data, currentItemList={}, user_name=""):
        i = 0
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
                if user_name == user:
                    user = ""
            # except:
            #     pass
            finally:
                pass
            print(i, key["name"], "(", key["type"],
                  Tools.sizeof_fmt(key["file_size"]), ")", user)
            # , key["id"], key["path"], key["type"], key["hash"]
            if type(key["file_size"]) == int:
                total += key["file_size"]
        if total > 0:
            print("Toltal:", Tools.sizeof_fmt(total))

    def print_file_menu(self, ):
        print("i - info")
        print("D - download")

    def file_info_print(self, _data):
        print("name: ", _data["name"])
        print("file_size: ", Tools.sizeof_fmt(int(_data["file_size"])))
        print("hash: ", _data["hash"])
        print(_data)
        input("press any key to continue")

    def interactiveMode(self):
        folder_selected = True
        current_folder = "root"
        # prevFolder = ""

        current_hash = "root"
        # prevHash = ""

        stack_hash = []   # deque()
        stack_names = []  # deque()

        currentItemList = {}
        file_info = None

        while True:
            # global folder_selected
            # global current_hash
            # global current_folder
            # global file_info
            clear()
            # print(stack_hash)
            self.print_menu(self.thunder_client, folder_selected,
                            current_folder, stack_hash)
            if self.thunder_client.logged_in:
                if folder_selected:
                    self.print_items(self.thunder_client.last_resp,
                                     currentItemList,
                                     self.thunder_client.user_name)
                else:
                    self.print_file_menu()    # folder meniu

            cmd = input("cmd: ")

            if cmd == "q":
                sys.exit(0)
            elif cmd == "i":
                self.file_info_print(file_info)
            elif cmd == "D":
                self.thunder_client.download_file_with_retry(file_info)
            # elif cmd == "U":
            #     upload_file()
            # elif cmd == "l":
            #     if not logged_in:
            #         doLogin()
            #     get_folders("root")
            elif cmd == "SDA":
                self.thunder_client.\
                    download_all_search_results(self.thunder_client.last_resp)
            elif cmd == "s":
                q = input("query: ")
                self.thunder_client.get_search_rez(q)
                stack_hash.append(current_hash)
                stack_names.append(current_folder)
                # current_hash = q
                # #prevFolder = current_folder
                # current_folder = rr["name"]
            elif cmd == "u":
                current_hash = stack_hash.pop()
                self.thunder_client.get_folders(current_hash)
                current_folder = stack_names.pop()
                folder_selected = True
            else:
                rr = currentItemList.get(cmd, None)
                if rr is None:
                    print("?????")
                else:
                    if rr["type"] == "folder":
                        self.thunder_client.get_folders(rr["hash"])
                        folder_selected = True
                        file_info = None
                    else:
                        folder_selected = False
                        file_info = rr

                    stack_hash.append(current_hash)
                    stack_names.append(current_folder)
                    # prevHash = current_hash
                    current_hash = rr["hash"]
                    # prevFolder = current_folder
                    current_folder = rr["name"]


def param_mode_help():
    print("--search= - phrase to search")
    print("--list - list founded files")
    print("--prompt - stops before download")
    print("--uploadfile=file.txt")
    print("--uploadmode - example:")
    print("     thunderdrive.py --uploadmode file1 file2 ...")
    print("--downloadmode - example:")
    print("     thunderdrive.py --downloadmode file1 file2 ...")
    print("--targetdir=THdir - target directory in thinderdrive.io for upload")


def param_mode(argv_full, logger):
    # print(argv_full)
    argv = argv_full[1:]
    # print(argv)

    search_phrases = []
    use_proxy = False
    list_files = False
    prompt = False
    upload = False
    download = False
    interactive = False
    # filename = ""
    upl_file_names = []
    target_directory = None

    try:
        opts, args = \
            getopt.getopt(argv, "h",
                          ["search=", "useproxy", "list",
                           "prompt", "help", "interactive",
                           "uploadmode", "downloadmode",
                           "uploadfile=", "targetdir="]
                          )
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)
    # print(opts, args)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            param_mode_help()
            sys.exit(0)
        elif opt == "--downloadmode":
            download = True
            search_phrases = args
        elif opt == "--search":
            download = True
            search_phrases.append(arg)
        # elif opt in ("--disableproxy"):
        #     disableproxy = True
        elif opt in ("--list"):
            list_files = True
        elif opt in ("--prompt"):
            prompt = True
            list_files = True
        elif opt == "--uploadmode":
            upload = True
            upl_file_names = args
        elif opt == "--uploadfile":
            upload = True
            upl_file_names.append(arg)
        elif opt in ("--tdir", "--targetdir"):
            target_directory = arg
        elif opt in ("--interactive"):
            interactive = True
        elif opt in ("--useproxy"):
            use_proxy = True

    https = http = None
    ssl_verify = True
    if use_proxy:
        https = "https://192.168.10.4:58080"
        http = "http://192.168.10.4:58080"
        ssl_verify = False

    usr, psw = get_login_info()
    thunder_client = ThunderDriveAPI(usr, psw, logger, https_proxy=https,
                                     http_proxy=http, ssl_verify=ssl_verify)
    thunder_client.tries = 1

    if interactive:
        InteractiveMode(thunder_client)
        sys.exit(0)

    if upload:
        folder_id = folder_hash = ""
        if target_directory is not None:
            folder_id, folder_hash =\
                thunder_client.find_folder_id(target_directory)
        thunder_client.upload_file_with_retry(upl_file_names, folder_id,
                                              folder_hash)
        sys.exit(0)

    if download:
        for search_phrase in search_phrases:
            thunder_client.get_search_rez(search_phrase)
            if list_files:
                InteractiveMode.print_items(_data=thunder_client.last_resp,
                                            user_name=thunder_client.user_name)
            if prompt:
                input("press any key to continue download; ctrl+C - to stop")
            thunder_client.\
                download_all_search_results(thunder_client.last_resp)
        logger.info("All files downloaded")
        sys.exit(0)


def get_login_info():
    usr = None
    psw = None
    usrDir = os.path.expanduser("~")
    config = configparser.ConfigParser()
    if os.path.exists("./config.txt"):
        config.read("./config.txt")
    elif os.path.exists(usrDir + "/config.txt"):
        config.read(usrDir + "/config.txt")
    else:
        raise FileExistsError('File not found: (./config.txt; ~/config.txt)')
    usr = config.get("thunderdrive", "username")
    psw = config.get("thunderdrive", "password")
    return usr, psw


def prep_logger():
    handlers = []
    # file_handler = logging.FileHandler(filename='/tmp/thunderdrive.log')
    # handlers.append(file_handler)
    stdout_handler = logging.StreamHandler(sys.stdout)
    handlers.append(stdout_handler)

    if len(handlers) == 0:
        return None
    format =\
        '[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=format,
        handlers=handlers
    )

    stdout_handler.setFormatter(logging.Formatter('%(message)s'))
    logger = logging.getLogger()
    return logger


if __name__ == "__main__":
    logger = prep_logger()
    try:
        if len(sys.argv) > 1:
            param_mode(sys.argv, logger)
        else:
            param_mode_help()
    except KeyboardInterrupt:
        print()
        sys.exit(50)
    except Exception as ex:
        print()
        if logger is not None:
            logger.exception("")
        else:
            print(ex)
        sys.exit(1)
    finally:
        pass

sys.exit(0)
