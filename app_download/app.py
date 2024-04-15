import os
import sys
import traceback
import threading
import json
import requests
import shutil
from datetime import datetime, timedelta
from urllib.parse import urljoin
from configparser import ConfigParser
from wand.image import Image
import sentry_sdk
from sentry_sdk import capture_exception, capture_message

from data_extractors.allianz_extractor import AllianzExtractor
from data_extractors.axa_extractor import AxaExtractor
from data_extractors.rest_extractor import RestExtractor
from data_extractors.scc_extractor import SccExtractor

from data_logger.data_logger import DataLogger
logger = DataLogger.get_logger(__name__)

TEMP_NO_LOGO_PATH = '/web_apps/app_download/extracted/no_logo/'
CONFIG_FILE = 'configs/config.ini'
CODES_DIR = 'codes'
DATA_DIR = 'extracted'

sentry_sdk.init(
    os.environ.get('CONFIG_DSN'),
    environment=os.environ.get('CONFIG_ENVIRONMENT', 'PRD'),
    server_name=os.environ.get('CONFIG_HOSTNAME', 'azs.mojedane.net'),
    #debug=True,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=float(os.environ.get('CONFIG_SENTRY_SAMPLE_RATE', 1.0)),
)


class Application:
    def __init__(self, config_file, codes_dir):
        self.allianz_codes_file = os.path.join(CODES_DIR, 'allianz.codes')
        self.axa_codes_file = os.path.join(CODES_DIR, 'axa.codes')
        self.rest_codes_file = os.path.join(CODES_DIR, 'rest.codes')
        self.scc_codes_file = os.path.join(CODES_DIR, 'scc.codes')

        self.allianz_extractor = AllianzExtractor(
            DATA_DIR,
            os.path.join(CODES_DIR, 'allianz.codes'),
        )
        self.axa_extractor = AxaExtractor(
            DATA_DIR,
            os.path.join(CODES_DIR, 'axa.codes'),
        )
        self.rest_extractor = RestExtractor(
            DATA_DIR,
            os.path.join(CODES_DIR, 'rest.codes'),
        )
        self.scc_extractor = SccExtractor(
            DATA_DIR,
            os.path.join(CODES_DIR, 'scc.codes'),
        )

        config = ConfigParser()
        config.read(CONFIG_FILE)
        api_url = config.get('server', 'api_url')

        self.auctions_api = urljoin(api_url, 'auctions/')

    def run(self):
        logger.info('[Downloader] Started downloading updates...')
        print('[Downloader] Started downloading updates...')
        self.download_updates()
        logger.info('[Downloader] Finished downloading updates...')
        print('[Downloader] Finished downloading updates...')

        logger.info('[Uploader] Started uploading updates...')
        print('[Uploader] Started uploading updates...')
        self.upload_updates()
        logger.info('[Uploader] Finished uploading updates...')
        print('[Uploader] Finished uploading updates...')

    def download_updates(self):
        allianz_task = threading.Thread(
            target=self.allianz_extractor.get_data,
        )
        axa_task = threading.Thread(
            target=self.axa_extractor.get_data,
        )
        rest_task = threading.Thread(
            target=self.rest_extractor.get_data,
        )
        scc_task = threading.Thread(
            target=self.scc_extractor.get_data,
        )

        allianz_task.start()
        rest_task.start()
        scc_task.start()
        axa_task.start()

        allianz_task.join(600)
        rest_task.join(600)
        scc_task.join(600)
        axa_task.join(600)

    def _insert_watermark(self, image_path):
        try:
            with Image(filename=image_path) as background:
                with Image(filename='watermark.png') as watermark:
                    left_offset = (15)
                    top_offset = (background.height - watermark.height + 15)
                    background.watermark(
                        image=watermark,
                        transparency=0.75,
                        left=left_offset,
                        top=top_offset
                    )
                    background.save(filename=image_path)
            return True
        except Exception as e:
            capture_exception(e)
            return False
   
    def _upload_auction(self, path, auction_file):
        auction_file_path = os.path.join(path, auction_file)
        # load auction json info
        with open(auction_file_path, 'r') as f:
            car = json.load(f)
        # check if already uploaded
        if car.get('uploaded', False):
            # logger.info('[Uploader][%s][%s] The auction is already uploaded.' % (car['provider_name'], car['provider_id']))
            # print('[Uploader][%s][%s] The auction is already uploaded.' % (car['provider_name'], car['provider_id']))
            return None    
        # check if there is no image
        images = car.get('images', None)
        if images is None:
            logger.info('[Uploader][%s][%s] The auction uploading is aborted with no image.' % (car['provider_name'], car['provider_id']))
            print('[Uploader][%s][%s] The auction uploading is aborted with no image.' % (car['provider_name'], car['provider_id']))
            return None
        # prepare uploading photos
        photos = list()
        for img_filename in images:
            img_path = os.path.join(path, img_filename)
            # copy only SCC images to no_logo directory
            if car.get('provider_name', '') == 'scc':
                img_newpath = os.path.join(TEMP_NO_LOGO_PATH, img_filename)
                try:
                    shutil.copy2(img_path, img_newpath)
                except:
                    pass
            try:
                self._insert_watermark(img_path)
                photos.append((img_filename,open(img_path, 'rb'),))
            except FileNotFoundError as e1:
                continue
        car['data'] = json.dumps(car['data'])

        # send uploading api request
        session = requests.Session()
        config = ConfigParser()
        config.read(CONFIG_FILE)
        token = config.get('client', 'id')
        headers = {'Authorization': 'Token %s' % token}
        session.headers.update(headers)
        try:
            response = session.post(
                url=self.auctions_api,
                data=car,
                headers=headers,
                files=photos,
                allow_redirects=True,
                stream=True,
            )
            if response.status_code == 201:
                # update auction data
                car['uploaded'] = True
                with open(auction_file_path, 'w') as f:
                    json.dump(car, f)
                logger.info('[Uploader][%s][%s] The auction is successfully uploaded.' % (car['provider_name'], car['provider_id']))
                print('[Uploader][%s][%s] The auction is successfully uploaded.' % (car['provider_name'], car['provider_id']))
                return car
            else:
                print('[Uploader][%s][%s] The auction uploading is failed due to invalid auction' % (car['provider_name'], car['provider_id']))
                logger.error('[Uploader][%s][%s] The auction uploading is failed due to invalid auction' % (car['provider_name'], car['provider_id']))
                return None
        except Exception as e:
            print('[Uploader][%s][%s] The auction uploading is failed due to server error' % (car['provider_name'], car['provider_id']))
            logger.error('[Uploader][%s][%s] The auction uploading is failed due to server error' % (car['provider_name'], car['provider_id']))
            capture_exception(e)
            return None
        
    def upload_updates(self):
        # insurance_dirs = ['allianz', 'axa']
        insurance_dirs = ['rest', 'scc', 'allianz', 'axa']
        for directory in insurance_dirs:
            path = os.path.join(DATA_DIR, directory)
            auctions_filenames = [ each for each in os.listdir(path) if each.endswith('.json')]
            for auction_filename in auctions_filenames:
                car = self._upload_auction(path, auction_filename)
                if car is None:
                    continue
                # remove auction images
                for image in car.get('images', None):
                    try:
                        if car['provider_name'] == 'axa':
                            os.remove('/web_apps/app_download/extracted/axa/' + image)
                        if car['provider_name'] == 'allianz':
                            os.remove('/web_apps/app_download/extracted/allianz/' + image)
                        elif car['provider_name'] == 'scc':
                            os.remove('/web_apps/app_download/extracted/scc/' + image)
                        else: 
                            os.remove('/web_apps/app_download/extracted/rest/' + image)
                    except FileNotFoundError:
                        pass                

if __name__ == '__main__':
    app = Application(CONFIG_FILE, CODES_DIR)
    app.run()
