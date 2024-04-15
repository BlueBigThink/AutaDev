import random
import string
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
from datetime import timedelta
from random import randint
from configparser import ConfigParser
from .bet_controller import BetController
from web_app.utils import log_exception
import logging
logger = logging.getLogger(__name__)


CODES_FILE = '/web_apps/app_download/codes/scc.codes'
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


class SccBetController(BetController):
    def __init__(self, auction):
        self.codes = ConfigParser()
        self.codes.read(CODES_FILE)
        self.counter = 0
        self.session = requests.Session()
        self.map_attr = dict()
        self.state = dict()
        self.url_download = None
        self.standort = ''
        self.button_elem = None
        self.auction = auction
        self.current_price = 0
        self.current_last_date = None
    
    def bet(self, auction_obj, price, price_max, is_aggressive=False):
        data, next = self._get_next_car_data(
            self.last_form_id,
            self.last_button_left,
            self.last_fixgrid,
            self.last_modalpopup_car,
            self.last_get_url_car,
            last=True,
        )
        self.last_bet_button_id = data['bet_button_id']
        self.last_price_pane_id = data['price_pane_id']
        self.current_price = data['current_price']
        self.last_date = data['last_date']

        # jesli blad daty to zakladamy ze data < 60sek
        if self.current_last_date is None:
            logger.info("[BetAutomate][SCC][%s] The variable current_last_date is None" % auction_obj.provider_id)
            self.current_last_date = auction_obj.end_date - timedelta(seconds=1)

        # current price
        self.current_price = int(float(self.current_price))
        price_to_bet = 0
        # jesli brak ceny to wbijamy cene
        if self.current_price == 0:
            price_to_bet = price
            logger.info('[BetAutomate][SCC][%s] No price identified, betting - %s' % (auction_obj.provider_id, price_to_bet))
        # jesli Tomek licytowal i przebijamy o 200
        elif self.current_price % 10 == 5 and (self.current_price + 200) <= price_max:
            price_to_bet = max(self.current_price - 5 + 200 + 6, price)
            logger.info('[BetAutomate][SCC][%s] Some price already exists - Tommy\'s price: %s, price to bet: %s' % (auction_obj.provider_id, self.current_price, price_to_bet))
        elif self.current_price % 10 == 5:
            price_to_bet = 0
            logger.info('[BetAutomate][SCC][%s] Some price already exists - Tommy\'s price: %s and is much higher than price_max: %s' % (auction_obj.provider_id, self.current_price, price_max))
        # jesli ostatnia licytacja wbita w ciagu ostatnich 20sek i koncowka rozna od 6 to przebijamy o min 1 CHF
        elif self.current_last_date + timedelta(seconds=20) > auction_obj.end_date and self.current_price % 10 != 6:
            if  (self.current_price - self.current_price % 10 + 6) <= price_max and (self.current_price - self.current_price % 10 + 6) > self.current_price:
                price_to_bet = max(self.current_price - self.current_price % 10 + 6, price)
            elif (self.current_price - self.current_price % 10 + 10 + 6) <= price_max and (self.current_price - self.current_price % 10 + 10 + 6) > self.current_price:
                price_to_bet = max(self.current_price - self.current_price % 10 + 10 + 6, price)
            
            logger.info('[BetAutomate][SCC][%s] Some price already exists and bet before last 20seconds: %sCHF, beat at least 1CHF: %s' % (auction_obj.provider_id, self.current_price, price_to_bet))
        # jesli ostatnia licytacja wbita wczesniej niz w ciagu ostatnich 20sek to przebijamy o min 90 CHF
        elif self.current_price % 10 != 6:
            bet_diff = 90
            if  (self.current_price - self.current_price % 10 + bet_diff + 6) <= price_max and (self.current_price - self.current_price % 10 + bet_diff + 6) > self.current_price:
                price_to_bet = max(self.current_price - self.current_price % 10 + bet_diff + 6, price)
            elif (self.current_price - self.current_price % 10 + bet_diff + 10 + 6) <= price_max and (self.current_price - self.current_price % 10 + bet_diff + 10 + 6) > self.current_price:
                price_to_bet = max(self.current_price - self.current_price % 10 + bet_diff + 10 + 6, price)
            
            logger.info('[BetAutomate][SCC][%s] Some price already exists and bet in last 20seconds: %sCHF, beat at least 90 CHF: %s' % (auction_obj.provider_id, self.current_price, price_to_bet))
        # jesli aktualna cena jest mniejsza od ceny sugerowanej to wbijamy cene sugerowana
        elif self.current_price < price:
            price_to_bet = price
            logger.info('[BetAutomate][SCC][%s] Some price already exists: %sCHF and is much smaller than: %s' % (auction_obj.provider_id, self.current_price, price_to_bet))

        if price_to_bet == 0:
            logger.info('[BetAutomate][SCC][%s] Some price already exists: %sCHF and is much higher than price_max: %s - automate stopped...' % (auction_obj.provider_id, self.current_price, price_to_bet))
            return

        data_endpoint_next_car = {
            self.last_form_id: self.last_form_id,
            'cc_clientId': CLIENT_ID,
            '{}.action'.format(self.bet_button_id): 'invoke(80,7,110,25,1,false,false,false,1,109)',
            'ccstyle': 'cars',
            self.last_price_pane_id: price_to_bet,
            '{}.clientvisibleamount'.format(self.last_fixgrid): '9',
            '{}.width'.format(self.last_modalpopup_car): '800',
            '{}.height'.format(self.last_modalpopup_car): '750',
            'javax.faces.ViewState': '3489379567969466702:4278820262064180124',
            '{}.left'.format(self.last_modalpopup_car): '187',
            '{}.top'.format(self.last_modalpopup_car): '185',
            '{}.columnindexoflastselection'.format(self.last_fixgrid): '1',
            '{}.horizontalscrollposition'.format(self.last_fixgrid): '0',
            'cc_subpageId': '0',
        }

        if not is_aggressive:
            self.headers['eclnt-requestid'] = self._get_request_id()
            response = self.session.post(self.last_get_url_car, data_endpoint_next_car, headers=self.headers)
            logger.info('[BetAutomate][SCC][%s] The automate was not aggresive, bet finished, price to bet was: %s' % (auction_obj.provider_id, price_to_bet))
            return

        logger.info('[BetAutomate][SCC][%s] The automate is aggresive, price to bet: %s' % (auction_obj.provider_id, price_to_bet))
        req_sent = False
        now = datetime.datetime.now()
        while auction_obj.end_date > now:
            if auction_obj.end_date - now <= timedelta(seconds=0.5):
                self.headers['eclnt-requestid'] = self._get_request_id()
                response = self.session.post(self.last_get_url_car, data_endpoint_next_car, headers=self.headers)
                logger.info('[BetAutomate][SCC][%s] Aggresive attack - interval 0.2: %s' % (auction_obj.provider_id, price_to_bet))
                sleep(0.20)
            elif auction_obj.end_date - now <= timedelta(seconds=1):
                self.headers['eclnt-requestid'] = self._get_request_id()
                response = self.session.post(self.last_get_url_car, data_endpoint_next_car, headers=self.headers)
                logger.info('[BetAutomate][SCC][%s] Aggresive attack - interval 0.3: %s' % (auction_obj.provider_id, price_to_bet))
                sleep(0.30)
            elif auction_obj.end_date - now <= timedelta(seconds=2.5) and not req_sent:
                self.headers['eclnt-requestid'] = self._get_request_id()
                response = self.session.post(self.last_get_url_car, data_endpoint_next_car, headers=self.headers)
                req_sent = True
                logger.info('[BetAutomate][SCC][%s] Aggresive attack - interval 0.1: %s' % (auction_obj.provider_id, price_to_bet))
                sleep(0.1)
            else:
                sleep(0.1)
            now = datetime.datetime.now()

    def logout(self):
        # not really needed
        pass

    def login(self):
        data_login_pass = {
            'isiwebuserid': self.codes.get('account', 'login'),
            'isiwebpasswd': self.codes.get('account', 'pass'),
            'submit': 'Login',
        }
        response = self.session.post(URL_LOGIN, data=data_login_pass)
        doc = lxml.html.document_fromstring(response.text)
        td_elements = doc.xpath("//td[@class='logininfo']")
        try:
            code = td_elements[1].find('b').text
        except IndexError:
            code = td_elements[0].find('b').text

        data_login_acc = {
            'response': self.codes.get('codes', code),
            'submit': 'Login'
        }
        response = self.session.post(URL_LOGIN, data=data_login_acc)
        logger.info('[BetAutomate][SCC][%s] Successful login, status HTTP: %s' % (self.auction.provider_id, response.status_code))
        self.session.get(URL_GET_CARS)
        response = self.session.get(URL_GET_APPLET)

    def prepare(self):
        self.find_auction()

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
        self.map_attr['Leergewicht in kg'] = None    # + 1
        self.map_attr['Letzte MFK'] = None           # + 1
        self.map_attr['Reparaturkosten'] = None      # + 1
        self.map_attr['Katalogpreis'] = None      # + 1
        self.map_attr['Sonderausstattung'] = None      # + 1
        self.map_attr['Antriebsart'] = None      # + 1
        self.map_attr['Standort'] = None
        #self.map_attr['Current_Price'] = 0

        for i in range(len(labels)):
            label = labels[i]

            try:
                label_text = label.attrib['text']
            except KeyError as e:
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
        # TODO
        # implement state here for the current price

    def find_auction(self):
        # cars_data = list()
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
        }
        self.headers['eclnt-requestid'] = self._get_request_id(3)
        response = self.session.post(get_url_car, data_endpoint_car, headers=self.headers)
        self._make_map(response.text)
        doc = lxml.html.document_fromstring(response.text)
        buttons = doc.xpath("//dummy/modalpopup/row/pane/row/button")
        button_right = buttons[1].attrib['id']
        button_left = buttons[0].attrib['id']
        modalpopup_car = doc.xpath("//modalpopup")[0].attrib['id']
        fixgrid = doc.xpath("//scrollpane/row/fixgrid")[0].attrib['id']
        try:
            car_data = self._extract_data(doc)
        except Exception as e:
            log_exception(e)
            logger.critical(e, exc_info=True)

        try:
            enabled = buttons[1].attrib['enabled']
            if enabled == 'false':
                next = False
        except:
            pass

        if car_data['provider_id'] == self.auction.provider_id:
            data, next = self._get_next_car_data(
                form_id,
                button_right,
                fixgrid,
                modalpopup_car,
                get_url_car,
            )
            self.last_form_id = form_id
            self.last_fixgrid = fixgrid
            self.last_modalpopup_car = modalpopup_car
            self.last_get_url_car = get_url_car
            self.last_button = button_left
            return
                    
        self.counter = 4
        next = True

        # SAVE THE FOLLOWING STATE TO OBJECT STATE
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
                log_exception(e)
                traceback.print_exc()
        if data['provider_id'] == self.auction.provider_id:
            data, next = self._get_next_car_data(
                form_id,
                button_left,
                fixgrid,
                modalpopup_car,
                get_url_car,
            )
            self.last_form_id = form_id
            self.last_fixgrid = fixgrid
            self.last_modalpopup_car = modalpopup_car
            self.last_get_url_car = get_url_car
            self.last_button = button_right            
            return

    def _get_next_car_data(self, form_id, button_right, fixgrid, modalpopup_car, get_url_car, last=False):
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
            '{}.columnindexoflastselection'.format(fixgrid): '1',
            '{}.horizontalscrollposition'.format(fixgrid): '0',
            'cc_subpageId': '0',
        }

        self.headers['eclnt-requestid'] = self._get_request_id()
        response = self.session.post(get_url_car, data_endpoint_next_car, headers=self.headers)
        self.counter += 1
        doc = lxml.html.document_fromstring(response.text)
        buttons = doc.xpath("//dummy/modalpopup/row/pane/row/button")
        button_right = buttons[1].attrib['id']
        fixgrid = doc.xpath("//scrollpane/row/fixgrid")[0].attrib['id']
        try:
            car_data = self._extract_data(doc)
        except Exception as e:
            logger.warning('[BetAutomate][SCC][%s] Error while extracting' % self.auction.provider_id)
            logger.critical(e, exc_info=True)
        next = True
        try:
            enabled = buttons[1].attrib['enabled']
            if enabled == 'false':
                next = False
        except:
            pass

        return car_data, next

    def _get_text_or_state(self, doc, id_attr):
        try:
            data = doc.xpath("//label[@id='{}']".format(self.map_attr[id_attr]))[0].attrib['text']
            self.state[id_attr] = data
        except IndexError:
            data = self.state[id_attr]

        return data

    def _extract_data(self, doc):
        car_data = {}
        car_data['provider_id'] = self._get_text_or_state(doc, 'Auktion_nr')[12:]
        try:
            last_date_timestamp = doc.xpath("//label[contains(@id,'-g_10-g_50-g_53')]")[0].attrib['text']
            car_data['last_date'] = datetime.datetime.fromtimestamp(int(last_date_timestamp)/1000)
        except:
            car_data['last_date'] = None
        car_data['bet_button_id'] = doc.xpath("//button[@text='Gebot abgeben']")[0].attrib['id']
        try:
            car_data['price_pane_id'] = doc.xpath("//formattedfield")[0].attrib['id']
            car_data['current_price'] = doc.xpath("//formattedfield")[0].attrib['value']
        except:
            car_data['current_price'] = 0
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

def main():
    # # ctrl = SccBetController('280264')
    # ctrl.login()
    # ctrl.prepare()
    # ctrl.bet({'provider_id': '280264', 'end_date': datetime.datetime.strptime('04.03.2024 08:00', '%d.%m.%Y %H:%M')}, 20, 30)
    # ctrl.bet({'provider_id': '280264', 'end_date': datetime.datetime.strptime('04.03.2024 08:00', '%d.%m.%Y %H:%M')}, 30, 30)
    pass

if __name__ == "__main__":
    main()