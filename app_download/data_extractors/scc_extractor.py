import string
import random
import sys
import zipfile
from time import sleep
import traceback
import os
import json
import requests
import binascii
import lxml
import shutil
from lxml import html
import time
import datetime
from random import randint
from configparser import ConfigParser
from sentry_sdk import capture_exception
from data_logger.data_logger import DataLogger
import bs4
from bs4 import BeautifulSoup
logger = DataLogger.get_logger(__name__)

CLIENT_OS = 'Windows 7'
CLIENT_ID = 'abcdefghPC'
CLIENT_NAME = 'root'
#CLIENT_IP = 'fe80:0:0:0:3873:a012:4d14:d51d%net6'
CLIENT_IP = '192.168.0.11'

URL_LOGIN = "https://secure.swisscrashcars.ch/cars/?login&language=en"
URL_GET_CARS = "https://secure.swisscrashcars.ch/cars/"
URL_GET_APPLET = "https://secure.swisscrashcars.ch/cars/main.ccapplet"


# not needed now
URL_INDEX = "https://secure.swisscrashcars.ch/cars/main.ccapplet?login&language=en"
URL_APPLET = "https://secure.swisscrashcars.ch/cars/main.ccapplet"
URL_CAR = "https://secure.swisscrashcars.ch/cars/faces/main.jsp"

TARGET_DIR = 'scc'
FINAL_LOGS = {
    "all_count": 0,
    "downloaded_count": 0,
    "success": False,
    "error": "",
    "time": datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
}

def save_final_logs():
    with open("/web_apps/app_download/scc.status", "w") as f:
        json.dump(FINAL_LOGS, f)

class SccExtractor():
    def __init__(self, dir_path, codes_file):
        # load scraper credentials
        self.codes = ConfigParser()
        self.codes.read(codes_file)
        self.counter = 0
        self.session = requests.Session()
        self.data_path = os.path.join(dir_path, TARGET_DIR)
        self.map_attr = dict()
        self.state = dict()
        self.url_download = None
        self.standort = ''
        self.button_elem = None

        try:
            os.mkdir(self.data_path)
        except FileExistsError:
            pass

    def get_data(self):
        '''
        Returns json list of objects:
        '''
        try:
            self._login()
            self._get_cars_data()
            FINAL_LOGS["success"] = True
            save_final_logs()
        except Exception as e:
            capture_exception(e)
            FINAL_LOGS["success"] = False
            save_final_logs()
            raise e

    def _login(self):
        # login scc site
        data_login_pass = {
            'isiwebuserid': self.codes.get('account', 'login'),
            'isiwebpasswd': self.codes.get('account', 'pass'),
            'submit': 'Login',
        }
        response = self.session.post(URL_LOGIN, data=data_login_pass)

        soup = BeautifulSoup(response.text, "lxml")
        result = soup.find(class_="logininfo")
        #print(result)
        try:
            code = result.find('b').text
            #print(code)
        except Exception as e:
            capture_exception(e)

        data_login_acc = {
            'response': self.codes.get('codes', code),
            'submit': 'Login'
        }

        response = self.session.post(URL_LOGIN, data=data_login_acc)
        self.session.get(URL_GET_CARS)
        self.session.get(URL_GET_APPLET)

        if response.status_code != 200:
            capture_exception("[SCC] Login failed")

    def _make_map(self, response_text):
        doc = lxml.html.document_fromstring(response_text)
        labels = doc.xpath("//form//label")
        texts = doc.xpath("//form//textpane")

        self.map_attr['Auktion_nr'] = None       # ==   # Auktion Nr. 157554
        self.map_attr['Auktionsende'] = None     # + 2
        self.map_attr['Fahrzeugart'] = None      # + 1
        self.map_attr['Marke'] = None            # + 1
        self.map_attr['Modell'] = None            # + 1
        self.map_attr['Typ'] = None              # + 1
        self.map_attr['1. Inverkehrsetzung'] = None  # + 1
        self.map_attr['Zählerstand'] = None          # + 1
        self.map_attr['Typenschein-Nr.'] = None      # + 1
        self.map_attr['VIN'] = None                  # + 1
        self.map_attr['Motorart'] = None             # + 1
        self.map_attr['Getriebeart'] = None          # + 1
        self.map_attr['Leistung'] = None             # + 1
        self.map_attr['Hubraum'] = None              # + 1
        self.map_attr['Zeitwert'] = None              # + 1
        self.map_attr['Leergewicht in kg'] = None    # + 1
        self.map_attr['Letzte MFK'] = None           # + 1
        self.map_attr['Reparaturkosten'] = None      # + 1
        self.map_attr['Katalogpreis'] = None      # + 1
        self.map_attr['Sonderausstattung'] = None      # + 1
        self.map_attr['Antriebsart'] = None      # + 1
        self.map_attr['Standort'] = None

        for i in range(len(labels)):
            label = labels[i]

            try:
                label_text = label.attrib['text']
            except KeyError:
                continue

            if label_text.startswith('Auktion Nr. '):
                self.map_attr['Auktion_nr'] = labels[i].attrib['id']
            elif label_text.startswith('Auktionsende'):
                self.map_attr['Auktionsende'] = labels[i+1].attrib['id']
            elif label_text in self.map_attr:
                self.map_attr[label_text] = labels[i+1].attrib['id']

        self.map_attr['Wichtige Hinweise'] = texts[0].attrib['id']
        self.map_attr['Beschädigungen'] = texts[1].attrib['id']
        self.map_attr['Ausstattung'] = texts[2].attrib['id']

    def need_updated(self, car_data):
        json_path = os.path.join(self.data_path, '{}.json'.format(car_data['provider_id']))
        if not os.path.isfile(json_path):
            return True
        with open(json_path, 'r') as f:
            car_json = json.load(f)
        date1 = datetime.datetime.strptime(car_json['end_date'], "%Y-%m-%d %H:%M:%S")
        date2 = datetime.datetime.strptime(car_data['end_date'], "%Y-%m-%d %H:%M:%S")
        time_diff = date2 - date1
        seconds_diff = time_diff.total_seconds()
        if seconds_diff > -100 and seconds_diff < 100:
            return False
        return True

    def _get_cars_data(self):
        cars_data = list()
        url_endpoint = "https://secure.swisscrashcars.ch/cars/faces/main.jsp"
        data_endpoint = {
            'cc_clearDump': 'true',
            'cc_initialCall': 'true',
            'cc_subpageId': '0',
            'cc_clientId': CLIENT_ID,
        }

        instance_id = self._create_instace_id()

        self.headers = {
            'User-Agent': 'Mozilla/4.0 (Linux 4.8.0-52-generic) Java/1.8.0_131',
            'eclnt-country': 'US',
            'eclnt-orientation': 'ltr',
            'eclnt-timezone': 'CET',
            'eclnt-height': '946',
            'eclnt-osarch': 'amd64',
            'eclnt-clientjavatype': 'swing',
            'eclnt-requestid': self._get_request_id(1),  # important!
            'eclnt-ip': CLIENT_IP,
            'eclnt-scale': '1.0',
            'eclnt-width': '941',
            'eclnt-font': 'Dialog',
            'eclnt-language': 'en',
            'eclnt-instanceid': instance_id,
            'eclnt-osname': 'Linux',
            'eclnt-username': CLIENT_NAME,
            'eclnt-client': 'applet',
            'eclnt-id': CLIENT_ID,
            'eclnt-originalurl': 'https://secure.swisscrashcars.ch:443/cars/faces/main.jsp',
            'eclnt-hostname': CLIENT_IP,

        }
        response = self.session.post(url_endpoint, headers=self.headers, verify=False, data=data_endpoint)
        doc = lxml.html.document_fromstring(response.text)
        get_url_car = URL_CAR

        form_id = doc.xpath("//form")[0].attrib['name']
        pane_id = doc.xpath("//pane[@invokeevent='click']")[0].attrib['id']
        data_endpoint_car = {
            'ccstyle': 'cars',
            form_id: form_id,
            '{}.action'.format(pane_id): 'invoke(100,45,348,62,1,false,false,false,1)',
            '{}'.format(pane_id): '0;0',
            '{}'.format(pane_id): '0;0',
            '{}.actionbefore'.format(pane_id): 'rowselect(0,1,false,false,false,1)',
            '{}.clientvisibleamount'.format(pane_id): '9',
            '{}.columnindexoflastselection'.format(pane_id): '1',
            '{}.horizontalscrollposition'.format(pane_id): '0',
            'javax.faces.ViewState': '-7151215068571054955:-2237429730697340865',
            'cc_subpageId': '0',
            'cc_clientId': CLIENT_ID,
            #'ccsessioncheckid': ccsessioncheckid
        }

        self.headers['eclnt-requestid'] = self._get_request_id(3)
        response = self.session.post(get_url_car, data_endpoint_car, headers=self.headers)
        self._make_map(response.text)
        doc = lxml.html.document_fromstring(response.text)
        buttons = doc.xpath("//dummy/modalpopup/row/pane/row/button")
        button_right = buttons[1].attrib['id']
        modalpopup_car = doc.xpath("//modalpopup")[0].attrib['id']
        fixgrid = doc.xpath("//scrollpane/row/fixgrid")[0].attrib['id']

        FINAL_LOGS['all_count'] += 1
        try:
            car_data = self._extract_data(response.text)
        except Exception as e:
            capture_exception(e)

        json_path = os.path.join(self.data_path, '{}.json'.format(car_data['provider_id']))

        if not os.path.isfile(json_path) or not self.url_download:
            try:
                car_data['images'] = self._get_images_data(response.text, form_id, fixgrid, get_url_car, car_data['provider_id'])
            except Exception as e:
                capture_exception(e) 
                car_data['images'] = list()

            json_name = "{}.json".format(car_data['provider_id'])
            json_path = os.path.join(self.data_path, json_name)

            FINAL_LOGS['downloaded_count'] += 1
            if self.need_updated(car_data):
                with open(json_path, "w") as f:
                    json.dump(car_data, f)
                logger.info('[Downloader][SCC][%s] New auction downloaded' % car_data['provider_id'])
                print('[Downloader][SCC][%s] New auction downloaded' % car_data['provider_id'])
            else:
                logger.info('[Downloader][SCC][%s] The auction was already downloaded - cancelling...' % car_data['provider_id'])
                print('[Downloader][SCC][%s] The auction was already downloaded - cancelling...' % car_data['provider_id'])    
        else:
            FINAL_LOGS['downloaded_count'] += 1
            logger.info('[Downloader][SCC][%s] The auction was already downloaded - cancelling...' % car_data['provider_id'])
            print('[Downloader][SCC][%s] The auction was already downloaded - cancelling...' % car_data['provider_id'])

        next = True

        try:
            enabled = buttons[1].attrib['enabled']
            if enabled == 'false':
                next = False
        except:
            pass

        self.counter = 4

        while next:
            try:
                data, next = self._get_next_car_data(
                    form_id,
                    button_right,
                    fixgrid,
                    modalpopup_car,
                    get_url_car,
                )
            except Exception as e:
                capture_exception(e)

    def _get_next_car_data(self, form_id, button_right, fixgrid, modalpopup_car, get_url_car):
        car_data = {}
        data_endpoint_next_car = {
            form_id: form_id,
            'cc_clientId': CLIENT_ID,
            '{}.action'.format(button_right): 'invoke(79,19,118,30,1,false,false,false,1)',
            'ccstyle': 'cars',
            '{}.clientvisibleamount'.format(fixgrid): '9',
            '{}.width'.format(modalpopup_car): '800',
            '{}.height'.format(modalpopup_car): '750',
            'javax.faces.ViewState': '3489379567969466702:4278820262064180124',
            '{}.left'.format(modalpopup_car): '187',
            '{}.top'.format(modalpopup_car): '185',
            #'ccsessioncheckid': self.headers['ccsessioncheckid'],
            '{}.columnindexoflastselection'.format(fixgrid): '1',
            '{}.horizontalscrollposition'.format(fixgrid): '0',
            'cc_subpageId': '0',
        }

        FINAL_LOGS['all_count'] += 1
        self.headers['eclnt-requestid'] = self._get_request_id()
        response = self.session.post(get_url_car, data_endpoint_next_car, headers=self.headers)
        self.counter += 1

        doc = lxml.html.document_fromstring(response.text)
        buttons = doc.xpath("//dummy/modalpopup/row/pane/row/button")
        #button_right = buttons[1].attrib['id']
        fixgrid = doc.xpath("//scrollpane/row/fixgrid")[0].attrib['id']

        try:
            car_data = self._extract_data(response.text)
        except Exception as e:
            capture_exception(e)

        json_path = os.path.join(self.data_path, '{}.json'.format(car_data['provider_id']))

        if not os.path.isfile(json_path) or not self.url_download:
            try:
                car_data['images'] = self._get_images_data(response.text, form_id, fixgrid, get_url_car, car_data['provider_id'])
            except Exception as e:
                capture_exception(e)
                car_data['images'] = list()

            json_name = "{}.json".format(car_data['provider_id'])
            json_path = os.path.join(self.data_path, json_name)
            
            FINAL_LOGS['downloaded_count'] += 1
            if self.need_updated(car_data):
                with open(json_path, "w") as f:
                    json.dump(car_data, f)
                logger.info('[Downloader][SCC][%s] New auction downloaded' % car_data['provider_id'])
                print('[Downloader][SCC][%s] New auction downloaded' % car_data['provider_id'])
            else:
                logger.info('[Downloader][SCC][%s] The auction was already downloaded - cancelling...' % car_data['provider_id'])
                print('[Downloader][SCC][%s] The auction was already downloaded - cancelling...' % car_data['provider_id'])    
        else:
            FINAL_LOGS['downloaded_count'] += 1
            logger.info('[Downloader][SCC][%s] The auction was already downloaded - cancelling...' % car_data['provider_id'])
            print('[Downloader][SCC][%s] The auction was already downloaded - cancelling...' % car_data['provider_id'])

        next = True
        try:
            enabled = buttons[1].attrib['enabled']
            if enabled == 'false':
                next = False
        except:
            pass

        try:
            button_right = buttons[1].attrib['id']
        except:
            next = False

        return car_data, next

    def _get_filedownload(self, doc, fixgrid, form_id):
        if not self.button_elem:
            self.button_elem = doc.xpath("//button[@image='/images/download.png']")[0].attrib['id']
        self.headers['eclnt-requestid'] = self._get_request_id()
        data = {
            '{}.action'.format(self.button_elem): 'invoke(46,14,74,25,1,false,false,false,1,200)',
            form_id: form_id,
            #'{}'.format(button_elem): '0;0',
            #'{}'.format(button_elem): '0;0',
            #'{}.actionbefore'.format(button_elem): 'rowselect(0,1,false,false,false,1)',
            '{}.clientvisibleamount'.format(fixgrid): '9',
            '{}.columnindexoflastselection'.format(fixgrid): '1',
            '{}.horizontalscrollposition'.format(fixgrid): '0',
            'javax.faces.ViewState': '652505377047338344:-6597080093378312686',
            'cc_subpageId': '0',
            'cc_clientId': CLIENT_ID,
        }

        response = self.session.post(
            URL_CAR,
            headers=self.headers,
            data=data
        )
        doc = lxml.html.document_fromstring(response.content)

        url_download = URL_GET_CARS + doc.xpath("//jshowurl")[0].attrib['url']
        filename_download = url_download[-len('Fotos_196921.zip'):]

        return url_download, filename_download

    def _get_images_data(self, xml_string, form_id, fixgrid, get_url_car, provider_id):
        ''' Extract images from xml '''
        images = list()
        doc = lxml.html.document_fromstring(xml_string)
        modalpopup_car = doc.xpath("//modalpopup")[0].attrib['id']
        
        url_download, filename_download = self._get_filedownload(doc, fixgrid, form_id)
        xd = self.session.get(url_download, stream=True)

        with open('/tmp/%s.zip' % provider_id, 'wb') as f:
            xd.raw.decode_content = True
            shutil.copyfileobj(xd.raw, f)

        zip=zipfile.ZipFile('/tmp/%s.zip' % provider_id)
        images = zip.namelist()
        zip.extractall(self.data_path)
        os.remove('/tmp/%s.zip' % provider_id)

        return images

    def _get_text_or_state(self, doc, id_attr):
        try:
            data = doc.xpath("//label[@id='{}']".format(self.map_attr[id_attr]))[0].attrib['text']
            self.state[id_attr] = data
        except KeyError as e:
            # DEFAULT VALUES HERE
            if id_attr == '1. Inverkehrsetzung':
                data = '0'
                self.state[id_attr] = data
            else:
                data = ''
                self.state[id_attr] = data
        except IndexError as e:
            data = self.state[id_attr]

        return data

    def _extract_data(self, xml_string):
        car_data = {}
        done = list()
        doc = lxml.html.document_fromstring(xml_string)

        car_data['provider_id'] = self._get_text_or_state(doc, 'Auktion_nr')[12:]
        done.append('Auktion_nr')
        brand = self._get_text_or_state(doc, 'Marke')
        done.append('Marke')
        model = self._get_text_or_state(doc, 'Modell')
        done.append('Modell')
        typ = self._get_text_or_state(doc, 'Typ')
        done.append('Typ')
        model += ' ' + typ
        car_data['title'] = brand + ' ' + model
        standort_a = ''
        try:
            standort_a = self._get_text_or_state(doc, 'Standort')
        except:
            standort_a = ''

        if standort_a != '':
            self.standort = standort_a
        else:
            standort_a = self.standort

        end_date = self._get_text_or_state(doc, 'Auktionsende')
        done.append('Auktionsende')
        car_data['end_date'] = datetime.datetime.fromtimestamp(int(end_date)/1000).strftime("%Y-%m-%d %H:%M:%S")
        end_year = datetime.datetime.fromtimestamp(int(end_date)/1000).strftime("%Y-%m")

        car_data['start_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        car_data['images_count'] = -1
        car_data['provider_name'] = 'scc'
        car_data['brand_name'] = brand
        prod_date = self._get_text_or_state(doc, '1. Inverkehrsetzung')
        done.append('1. Inverkehrsetzung')

        try:
            car_data['production_date'] = datetime.datetime.fromtimestamp(int(prod_date)/1000).strftime("%Y-%m-%d")
        except ValueError:
            car_data['production_date'] = datetime.datetime.now().strftime("%Y-%m-%d")

        car_data['run'] = int(float(self._get_text_or_state(doc, 'Zählerstand')))
        car_data['data'] = dict()
        car_data['data']['Standort'] = standort_a

        for attr_id in self.map_attr:
            if attr_id in done:
                continue

            try:
                data_entry = self._get_text_or_state(doc, attr_id)
                car_data['data'][attr_id] = data_entry
                continue
            except Exception as e:
                pass

            try:
                data_entry = doc.xpath("//form//textpane[@id='{}']".format(self.map_attr[attr_id]))[0].attrib['text']
                car_data['data'][attr_id] = data_entry
                continue
            except Exception as e:
                pass

        return car_data

    def _create_instace_id(self):
        instance_id = '{}_{}'.format(
            int(round(time.time() * 1000)) + 29763,
            randint(1000000, 9999999)
        )

        return instance_id

    def _get_request_id(self, num=None):
        num = num or self.counter

        request_id = "{}_{}".format(  
            randint(1000000, 9999999),
            num
        )

        return request_id


if __name__ == '__main__':
    ext = SccExtractor('../codes/scc.codes')
    ext.get_data()
