import os
import re
import json
import imaplib
import email
import time
from configparser import ConfigParser
from datetime import datetime, timedelta
from playwright.sync_api import expect, sync_playwright
# from extractor_controller import ExtractorController
from data_extractors.extractor_controller import ExtractorController
from sentry_sdk import capture_exception
from data_logger.data_logger import DataLogger
logger = DataLogger.get_logger(__name__)

LOGIN_URL = 'https://www.allianz-carauction.ch/login.html'
MAIN_URL = 'https://www.allianz-carauction.ch/auction.html'
SESSION_FILE = "allianz.session"
TARGET_DIR = 'allianz'

class AllianzExtractor(ExtractorController):

    def __init__(self, dir_path, code_files):
        self.codes = ConfigParser()
        self.codes.read(code_files)
        data_path = os.path.join(dir_path, TARGET_DIR)
        try:
            os.mkdir(data_path)
        except FileExistsError:
            pass
        self.data_path = data_path
        self.car_infos = []
    
    def get_verification_code(self):
        logger.info('[Downloader][ALLIANZ] Wait verification...')
        print('[Downloader][ALLIANZ] Wait verification...')
        # Connect to the email server
        mail = imaplib.IMAP4_SSL(self.codes.get("email", "imap"))
        # specify your IMAP server here
        mail.login(self.codes.get("email", "username"), self.codes.get("email", "pass"))
        mail.select("inbox")
            
        # Define the time threshold (e.g., emails sent after this time will be fetched)
        # time_threshold = datetime.now() - timedelta(minutes=62)
        time_threshold = datetime.now() - timedelta(minutes=121)

        # time_threshold_str = time_threshold.strftime("%d-%b-%Y %H:%M:%S")
        time_threshold_str = time_threshold.strftime("%d-%b-%Y")
        found = False
        while not found:
            self.page.wait_for_timeout(1000)
            # Search for emails sent after the specified time
            status, messages = mail.search(None, f'(SINCE "{time_threshold_str}")')
            mail_ids = messages[0].split()

            # Loop through the email IDs and fetch the corresponding emails
            for mail_id in mail_ids:
                status, msg_data = mail.fetch(mail_id, "(RFC822)")
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                email_time = datetime.strptime(email_message["Date"], "%a, %d %b %Y %H:%M:%S %z (%Z)").replace(tzinfo=None)
                if email_time < time_threshold :
                    continue
                verification_code = self._extract_verification_code(email_message)
                if verification_code:
                    print(verification_code)
                    found = True
                    break
        mail.logout()
        return verification_code
        
    def _extract_verification_code(self, email_message):
        pattern = r"Ihr MFA-Code lautet: (\d+)"
        result = None
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    match = re.search(pattern, text)
                    if match:
                        result = match.group(1)
                        break
        else:
            # If the email is not multipart, directly extract the body
            text = (email_message.get_payload(decode=True).decode("utf-8", errors="ignore"))
            match = re.search(pattern, text)
            if match:
                result = match.group(1)
        return result.strip()
    
    def _save_cookies(self):
        cookies = self.context.cookies()
        with open(SESSION_FILE, 'w') as file:
            file.write(str(cookies))

    def _load_cookies(self):
        try:
            # Read cookies from a file
            with open(SESSION_FILE, 'r') as file:
                cookies = eval(file.read())  # Note: Evaluate the string to convert it to a list
            self.context.add_cookies(cookies)
        except:
            pass

    def _login(self):
        login = self.codes.get('account', 'login')
        password = self.codes.get('account', 'password')
        self.page.get_by_placeholder('Benutzername').fill(login)
        self.page.get_by_placeholder('Passwort').fill(password)
        self.page.get_by_text("Anmelden", exact=True).click() 
        if self._is_main_page():
            self._save_cookies()
            return True
        elif self._is_verification_page():
            try:
                self.page.locator("input[name=\"mfaForm\\:mfaCode\"]").click()
                verification_code = self.get_verification_code()
                self.page.locator("input[name=\"mfaForm\\:mfaCode\"]").press_sequentially(verification_code)
                self.page.keyboard.press("Enter")
                self.page.wait_for_timeout(10000)
                if self._is_main_page():
                    self._save_cookies()
                    return True
                return False
                
            except Exception as e:
                print(e)
                self._save_cookies()
                return False
        else:
            return False

    def get_all_cars(self):
        start_time = time.time()
        while len(self.car_infos) == 0:
            self.page.wait_for_timeout(1000)
            if time.time() - start_time >= 180:
                print('[Downloader][ALLIANZ] Downloading failed due to server connection.')
                logger.info('[Downloader][ALLIANZ] Downloading failed due to server connection.')
                return
        for car_info in self.car_infos:
            if not self.update_needed(car_info):
                continue
            self.get_car_data(car_info)
    
    def get_car_data(self, car_info):
        for i in range(5):
            car_data = self._get_car_data(car_info)
            if car_data and self._check_car_images(car_data):
                self.save_car_json(car_data)
                return
        print(f"[Downloader][ALLIANZ][{car_info['provider_id']}] The auction downloading is failed due to error")
        return
             
    def _check_car_images(self, car_data):
        images = car_data.get('images', None)
        invalid_counts = 0
        for img_filename in images:
            img_path = os.path.join(self.data_path, img_filename)
            if not os.path.exists(img_path):
                invalid_counts += 1
            if os.path.getsize(img_path) < 2048:
                invalid_counts += 1
        if invalid_counts > 0:
            return False
        return True

    def _get_auction_enddate(self, auction_time_str):
        current_datetime = datetime.now()
        hours = minutes = seconds = 0 
        if len(auction_time_str.split(':')) == 2:
            minutes, seconds = map(int, auction_time_str.split(':'))
        elif len(auction_time_str.split(':')) == 3:
            hours, minutes, seconds = map(int, auction_time_str.split(':'))
        duration = timedelta(hours=hours, minutes=minutes, seconds=seconds) 
        result_datetime = current_datetime + duration
        if result_datetime.minute > 30:
            rounded_datetime = (result_datetime.replace(second=0, microsecond=0, minute=0) + timedelta(hours=1)).replace(minute=0)
        else:
            rounded_datetime= result_datetime.replace(minute=0, second=0, microsecond=0)
        return rounded_datetime
    
    def _get_car_data(self, car_info): 
        try: 
            ret_car = dict()
            ret_car['title'] = car_info['title']
            ret_car['start_date'] = None
            ret_car['end_date'] = car_info['end_date'].strftime("%Y-%m-%d %H:%M:%S")
            ret_car['provider_name'] = 'allianz'
            ret_car['provider_id'] = car_info['provider_id']
            ret_car['brand_name'] = car_info['title'].strip().split(' ')[0]
            ret_car['run'] = car_info['run']
            ret_car['production_date'] =  car_info['production_date'].strftime("%Y-%m-%d")
            ret_car['images_count'] = 0
            ret_car['images'] = list()
            car_data = {}

            # get image names and count
            self.page.goto(car_info['url'], timeout=90000, wait_until='domcontentloaded')
            self.page.wait_for_load_state('load', timeout=90000)
            self.page.wait_for_selector('#slider')
            for image_element in self.page.locator("#slider").get_by_role("listitem").all():
                image_id = image_element.get_attribute("data-id")
                if image_id:
                    ret_car["images"].append(f"{image_id}.jpg")
                    ret_car['images_count'] += 1

            # get extra info
            self.page.locator('.articledetail').wait_for()
            rows = self.page.locator('.articledetail').locator('tr')
            for row in rows.all():
                cells = row.locator('td').all()
                if (len(cells) >= 2):
                    key = cells[0].text_content()
                    value = cells[1].text_content()
                    car_data[key] = value

            self.page.locator('#description').wait_for()
            rows = self.page.locator('#description').locator('tr')
            for row in rows.all():
                cells = row.locator('td').all()
                if (len(cells) >= 2):
                    key = cells[0].text_content()
                    value = cells[1].text_content()
                    car_data[key] = value

            self.page.locator('#state').wait_for()
            rows = self.page.locator('#state').locator('tr')
            for row in rows.all():
                cells = row.locator('td').all()
                if (len(cells) >= 2):
                    key = cells[0].text_content()
                    value = cells[1].text_content()
                    car_data[key] = value

            car_data['Sonderausstattung'] = self.page.locator("#special").text_content()
            car_data['Serienausstattung'] = self.page.locator("#serien").text_content()
            ret_car['data'] = car_data
            return ret_car
        except Exception as e:
            print(e)
            return None

    def _is_main_page(self):
        try:
            expect(self.page.get_by_text("logout", exact=True)).to_be_visible()
            return True
        except:
            return False

    def _is_verification_page(self):
        try:
            expect(self.page.locator("#mfaDialog")).to_be_visible()
            return True
        except:
            return False

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


    def _download_cars(self, route):
        try:
            response = route.fetch()
            req_json = response.json()
            #with open(f"/tmp/allianz_{datetime.now().json}", 'wb') as f:
            #    f.write(response.body())
            current_datetime = datetime.now() + timedelta(seconds=10)
            for entry in req_json['list']:
                car = dict()
                car['title'] = entry.get('at', 'Unknown')
                car['provider_id'] = entry.get('a', 0)
                if entry.get('edt', None) is None:
                    if entry.get('et', 0) != 0:
                        car['end_date'] = (current_datetime + timedelta(seconds=entry.get('et', 0))).replace(second=0)
                else:
                    car['end_date'] = datetime.strptime(entry.get('edt', '').replace(' ', ''), "%d.%m.%Y-%H:%M")
                car['production_date'] = datetime.strptime(entry.get('r', '01/1997'), "%m/%Y")
                car['url'] = f"https://www.allianz-carauction.ch/{entry.get('au', '')}"
                car['run'] = entry.get('km', 0)
                self.car_infos.append(car)
            route.fulfill(response=response, json=req_json)
            self.context.unroute("https://www.allianz-carauction.ch/auction/list/DE")
        except Exception as err:
            capture_exception(err)  
                              
    def _download_images(self, route, request):
        if 'original=true' not in request.url:
            route.abort()
            return
        route.continue_()
        pattern = r"fileId=(\d+)"
        match = re.search(pattern, request.url)
        if match:
            result = match.group(1)
            with open(os.path.join(self.data_path, f"id_{result}.jpg"), 'wb') as file:
                file.write(request.response().body())    
  
   
    def get_data(self):
        logger.info('[Downloader][ALLIANZ] Start downloading...')
        print('[Downloader][ALLIANZ] Start downloading...')
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True,
                proxy= {
                    "server": self.codes.get("proxy", "server"),
                    "username": self.codes.get("proxy", "username"),
                    "password": self.codes.get("proxy", "password")
                }
            )
            self.context = self.browser.new_context()
            self.context.route("**/*.{png,jpg,jpeg}", lambda route: route.abort())
            self.context.route("https://www.allianz-carauction.ch/javax.faces.resource/dynamiccontent.properties.html?*", self._download_images)
            self.context.route("https://www.allianz-carauction.ch/auction/list/DE", self._download_cars)
            self._load_cookies()
            self.page = self.context.new_page()
            self.page.goto(MAIN_URL)
            if not self._is_main_page():
                logger.info('[Downloader][ALLIANZ] Sign in...')
                print('[Downloader][ALLIANZ] Sign in...')
                self.page.goto(LOGIN_URL, timeout=90000, wait_until='domcontentloaded')
                if not self._login() and not self._is_main_page():
                    print('[Downloader][ALLIANZ] Failed due to signing in... : ALLIANZ Server Error')
                    logger.info('[Downloader][ALLIANZ] Failed due to signing in... : ALLIANZ Server Error')
                    return
            self.get_all_cars()
            logger.info('[Downloader][ALLIANZ] Finish downloading')
            print('[Downloader][ALLIANZ] Finish downloading')
        except Exception as e:
            logger.error(f"[Downloader][ALLIANZ] Downloading failed due to error({str(e)})")
            print(f"[Downloader][ALLIANZ] Downloading failed due to error({str(e)})")
            capture_exception(e)
        self.context.close()
        self.browser.close()        
    
    def update_needed(self, car):
        try:
            is_updated = True
            car_json = self.get_car_json(car)
            if car_json:
                date1 = datetime.strptime(car_json['end_date'], "%Y-%m-%d %H:%M:%S")
                date2 = car.get('end_date', None)
                if date2 is None:
                    print(f"[Downloader][ALLIANZ][{car['provider_id']}] The auction was already downloaded - cancelling...")
                    logger.info(f"[Downloader][ALLIANZ][{car['provider_id']}] The auction was already downloaded - cancelling...")
                    return False
                time_diff = date2 - date1
                seconds_diff = time_diff.total_seconds()
                if seconds_diff > -100 and seconds_diff < 100:
                    print(f"[Downloader][ALLIANZ][{car['provider_id']}] The auction was already downloaded - cancelling...")
                    logger.info(f"[Downloader][ALLIANZ][{car['provider_id']}] The auction was already downloaded - cancelling...")
                    is_updated = False
                else:
                    print(f"[Downloader][ALLIANZ][{car['provider_id']}] The auction was updated from {date1.strftime('%Y-%m-%d %H:%M')} to {date2.strftime('%Y-%m-%d %H:%M')}")
                    logger.info(f"[Downloader][ALLIANZ][{car['provider_id']}] The auction was updated from {date1.strftime('%Y-%m-%d %H:%M')} to {date2.strftime('%Y-%m-%d %H:%M')}")
            else:
                print(f"[Downloader][ALLIANZ][{car['provider_id']}] New auction was downloaded")
                logger.info(f"[Downloader][ALLIANZ][{car['provider_id']}] New auction was downloaded")
            return is_updated
        except Exception as e:
            print(f"[Downloader][ALLIANZ][{car['provider_id']}] Auction checking is failed - {str(e)}")
            logger.info(f"[Downloader][ALLIANZ][{car['provider_id']}] Auction checking is failed - {str(e)}")
            capture_exception(e)
            return True

    
def main():
    extractor = AllianzExtractor('../extracted', '../codes/allianz.codes')
    extractor.get_data()

if __name__ == "__main__":
    main()
