import os
import json
from datetime import datetime
import requests
import hashlib
import shutil
from bs4 import BeautifulSoup
from configparser import ConfigParser
from sentry_sdk import capture_exception
from data_extractors.extractor_controller import ExtractorController
from data_logger.data_logger import DataLogger
logger = DataLogger.get_logger(__name__)


LOGIN_URL = 'https://www.restwertboerse.ch/index.php'
REST_MAIN = 'https://www.restwertboerse.ch{}'
OFFERS_URL = 'https://www.restwertboerse.ch/offers.php?page={}'
TARGET_DIR = 'rest'
FINAL_LOGS = {
    "all_count": 0,
    "downloaded_count": 0,
    "success": False,
    "error": "",
    "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}
CAR_LOGS = {
    "error": "",
    "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}
# REST_STATUS = "/web_apps/app_download/rest.status"
# REST_CAR_STATUS = "/web_apps/app_download/rest_car.status"
REST_STATUS = "./rest.status"
REST_CAR_STATUS = "./rest_car.status"

def save_final_logs():
    with open(REST_STATUS, "w") as f:
        json.dump(FINAL_LOGS, f)

def save_car_logs():
    with open(REST_CAR_STATUS, "w") as f:
        json.dump(CAR_LOGS, f)


class RestExtractor(ExtractorController):
    
    def __init__(self, dir_path, codes_file):
        # load config
        self.codes = ConfigParser()
        self.codes.read(codes_file)
        # create session for rest
        self.session = requests.Session()
        # create extracted folder
        data_path = os.path.join(dir_path, TARGET_DIR)
        try:
            os.mkdir(data_path)
        except FileExistsError:
            pass
        self.data_path = data_path

    def get_data(self):
        '''
        Returns json list of objects
        '''
        logger.info('[Downloader][REST] Start downloading...')
        print('[Downloader][REST] Start downloading...')
        try:
            logger.info('[Downloader][REST] Sign in...')
            print('[Downloader][REST] Sign in...')
            self._login()
            self._get_all_cars()
            self._login_vaudoise()
            self._get_all_cars(subproviders=['Vaudoise Assurances'])
            logger.info('[Downloader][REST] Finish downloading...')
            print('[Downloader][REST] Finish downloading...')
            FINAL_LOGS["success"] = True
            save_final_logs()
        except Exception as e:
            capture_exception(e)
            FINAL_LOGS["success"] = False
            save_final_logs()
            raise e

    def get_request(self, url):
        response = self.session.get(url)
        if response.status_code == 305:
            proxy_url = response.headers['Location']
            original_proxies = self.session.proxies.copy()
            self.session.proxies = {'http': proxy_url, 'https': proxy_url}
            redirected_response = self.session.get(url)
            self.session.proxies = original_proxies
            return redirected_response
        elif response.status_code == 303:
           redirected_url = response.headers['Location']
           redirected_response = requests.get(redirected_url)
           return redirected_response
        else:
            return response
    
    def get_car_json(self, car):
        try :
            json_path = os.path.join(self.data_path, f"{car['provider_id']}.json")
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    car_data = json.load(f)
                return car_data
        except Exception as e:
            capture_exception(e)
        return None

    def save_car_json(self, car_data):
        try : 
            json_path = os.path.join(self.data_path, f"{car_data['provider_id']}.json")
            with open(json_path, 'w') as f:
                json.dump(car_data, f)
        except Exception as e:
            capture_exception(e)

    def update_needed(self, car):
        try:
            is_updated = True
            car_json = self.get_car_json(car)
            if car_json:
                date1 = datetime.strptime(car_json['end_date'], "%Y-%m-%d %H:%M:%S")
                date2 = datetime.strptime(car['end_date'], "%d.%m.%Y, %H:%M")
                time_diff = date2 - date1
                seconds_diff = time_diff.total_seconds()
                if seconds_diff > -100 and seconds_diff < 100:
                    print(f"[Downloader][REST][{car['provider_id']}] The auction was already downloaded - cancelling...")
                    logger.info(f"[Downloader][REST][{car['provider_id']}] The auction was already downloaded - cancelling...")
                    is_updated = False
                else:
                    print(f"[Downloader][REST][{car['provider_id']}] The auction was updated from {date1.strftime('%Y-%m-%d %H:%M')} to {date2.strftime('%Y-%m-%d %H:%M')}")
                    logger.info(f"[Downloader][REST][{car['provider_id']}] The auction was updated from {date1.strftime('%Y-%m-%d %H:%M')} to {date2.strftime('%Y-%m-%d %H:%M')}")
            else:
                print(f"[Downloader][REST][{car['provider_id']}] New auction was downloaded")
                logger.info(f"[Downloader][REST][{car['provider_id']}] New auction was downloaded")
            return is_updated
        except Exception as e:
            print(f"[Downloader][REST][{car['provider_id']}] Auction checking is failed - {str(e)}")
            logger.info(f"[Downloader][REST][{car['provider_id']}] Auction checking is failed - {str(e)}")
            capture_exception(e)
            return True
        
    def _get_all_cars(self, subproviders=None):
        ''' Returns list of all url cars '''
        page = 1
        while True:
            response = self.get_request(OFFERS_URL.format(page))
            soup_cars = BeautifulSoup(response.text, 'html.parser')
            car_entries = soup_cars.find('tbody').find_all('tr')
            # if reach out the end page, skip
            if len(car_entries) == 0:
                break
            for car_entry in car_entries:
                current_subprovider = car_entry.find_all('td')[4].string
                if subproviders and current_subprovider not in subproviders:
                    continue
                FINAL_LOGS['all_count'] += 1
                car = dict()
                car['subprovider_name'] =car_entry.find_all('td')[4].string
                car['provider_id'] = car_entry['id']
                date_tag = car_entry.find_all('td')[3]
                car['end_date'] = date_tag.contents[0]
                car['url'] = car_entry.find('a')['href']
                if self.update_needed(car):
                    car_data = self.get_all_cars(car)
                    if car_data:
                        self.save_car_json(car_data)
            page += 1

    def get_all_cars(self, car_info):
        ''' Returns json for car '''
        try:
            if 'offer-files' in car_info['url']:
                provider_id = car_info['url'].split('?id=')[1]
                car_info['url'] = '/offer-detail?id=%s&m=all&page=' % provider_id

            car = dict()

            response = self.get_request(REST_MAIN.format(car_info['url']))
            soup_car = BeautifulSoup(response.text, 'html.parser')
            title = soup_car.h1.text.strip().split('\t')
            title = list(filter(None, title))

            if len(title) < 2:
                car['auction_nr'] = title[0][3:]
            else:
                car['auction_nr'] = title[1][3:]

            auction_end = soup_car.find_all('div', 'box-body')[2].find_all('p')[1]
            car['auction_end'] = auction_end.string.strip()

            fahr_tbody = soup_car.find('table', 'margin-bottom-20').find('tbody')

            for tr_entry in fahr_tbody.find_all('tr'):
                tds = tr_entry.find_all('td')

                if len(tds) == 2:
                    car[tds[0].string.strip()] = tds[1].string.strip() if tds[1].string else None
                elif len(tds) == 1:
                    car['Information'] = str(tds[0])
                    car['Information'] = car['Information'][len('<td colspan="2">'):-len('</td>')]

            werte_tbody = soup_car.find_all('table', 'margin-bottom-20')[1].find('tbody')
            for tr_entry in werte_tbody.find_all('tr'):
                tds = tr_entry.find_all('td')
                car[tds[0].string.strip()] = tds[1].string.strip() if tds[1].string else None

            car['Ausstattung'] = list()
            ausstattungs = soup_car.find_all('div', 'box-body')[1].find_all('i', 'green')
            for austattung in ausstattungs:
                name = austattung.nextSibling
                car['Ausstattung'].append(name)
            
            schadenb = soup_car.find('div', 'margin-top-20')
            if schadenb: 
                schadenb = str(schadenb)
                schadenb = schadenb.replace('/assets/images/graphics/car-side.png', '/static/website/img/car-side.png')
                schadenb = schadenb.replace('/assets/images/graphics/car-top.png', '/static/website/img/car-top.png')
                car['Schadenbeschrieb'] = schadenb

            ret_car = dict()
            ret_car['provider_id'] = car.pop('auction_nr', None)
            ret_car['end_date'] = datetime.strptime(car.pop('auction_end'), "%d.%m.%Y, %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")

            self.set_car_images(car, response.text)
            if car['Marke'] is None:
                car['Marke'] = 'N/A'
            if car['Typ'] is None:
                car['Typ'] = 'N/A'
            ret_car['title'] = "{} {}".format(car['Marke'], car['Typ'])
            ret_car['start_date'] = None
            ret_car['images_count'] = -1
            ret_car['provider_name'] = 'rest'
            ret_car['brand_name'] = car.pop('Marke', None)
            if car.get('1. Inv.', None) is None:
                car['1. Inv.'] =  datetime.now().strftime("%d.%m.%Y")
            try:
                production_date = datetime.strptime(car.pop("1. Inv.", datetime.now().strftime("%d.%m.%Y")), "%d.%m.%Y")
                if production_date < datetime(year=1900, month=1, day=1):
                    production_date = datetime(year=1997, month=1, day=1)
            except:
                production_date = datetime(year=1997, month=1, day=1)
            ret_car['production_date'] = production_date.strftime("%Y-%m-%d")
            ret_car['run'] = car.pop('Km', '0').replace('\'', '')
            ret_car['images'] = car.pop('images', list())
            ret_car['data'] = car
            ret_car['subprovider_name'] = car_info['subprovider_name']
            return ret_car
        except Exception as e:
            print(f"[Downloader][REST][{ret_car['provider_id']}] Auction downloading is skipped with error({e})")
            logger.info(f"[Downloader][REST][{ret_car['provider_id']}] Auction downloading is skipped with error({e})")
            capture_exception(e)
            return None
    
    def download_image(self, image):
        url = image['href']
        for i in range(3):
            try:
                img_data = self.session.get(REST_MAIN.format(url), stream=True, timeout=3)
                return img_data
            except:
                continue
        return None

    def set_car_images(self, car, html_string):
        ''' Assigns list of images '''

        car['images'] = list()
        soup_car = BeautifulSoup(html_string, 'html.parser')
        try:
            images = soup_car.find('ul', 'slides').find_all('a')
        except AttributeError as e:
            # NO IMAGES LOGGING HERE IF NEEDED
            car['images'] = list()
            return car

        for image in images:
            url = image['href']
            img_data = self.download_image(image)
            if img_data is None:
                print(f"[Downloader][REST][{car['provider_id']}] The auction image({url}) download was missed")
                logger.info(f"[Downloader][REST][{car['provider_id']}] The auction image({url}) download was missed")
                continue

            img_data.raw.decode_content = True
            url = url.replace('/', '_')
            img_path = os.path.join(self.data_path, url)
            with open(img_path, 'wb') as f:
                shutil.copyfileobj(img_data.raw, f)
            car['images'].append(url)

        return car

    def _login(self):
        password = self.codes.get('account', 'pass')
        m = hashlib.sha512()
        m.update(password.encode('utf-8'))
        hashed_pass = m.hexdigest()
        data = {
            'p1': hashed_pass,
            'username': self.codes.get('account', 'login'),
            'action': 'login',
            'ref': '',
            'agb': '1',
        }
        self.session = requests.Session()
        response = self.session.post(LOGIN_URL, data=data)
        if response.status_code != 200:
            raise Exception("Login Failed")

    def _login_vaudoise(self):
        password = self.codes.get('account_vaudoise', 'pass')
        m = hashlib.sha512()
        m.update(password.encode('utf-8'))
        hashed_pass = m.hexdigest()
        data = {
            'p1': hashed_pass,
            'username': self.codes.get('account_vaudoise', 'login'),
            'action': 'login',
            'ref': '',
            'agb': '1',
        }
        self.session = requests.Session()
        response = self.session.post(LOGIN_URL, data=data)
        if response.status_code != 200:
            raise Exception("Login Failed")

if __name__ == '__main__':
    ext = RestExtractor('../extracted', '../codes/rest.codes')
    ext.get_data()
