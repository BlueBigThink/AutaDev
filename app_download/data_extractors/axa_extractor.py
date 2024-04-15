import os
import re
import json
import time
import email
import imaplib
import requests
import requests
from datetime import datetime, timedelta
from configparser import ConfigParser
from playwright.sync_api import expect, sync_playwright
from sentry_sdk import capture_exception
# from data_extractors.extractor_controller import ExtractorController
from extractor_controller import ExtractorController
# from data_logger.data_logger import DataLogger
# logger = DataLogger.get_logger(__name__)

LOGIN_URL = "https://carauction.axa.ch/login.html"
MAIN_URL = "https://carauction.axa.ch/auction.html"
TARGET_DIR = "axa"
SESSION_FILE = "axa.session"

class AxaExtractor(ExtractorController):
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

    def _login(self):
        self.page.goto(LOGIN_URL)
        self.page.wait_for_load_state('load')
        login = self.codes.get('account', 'login')
        password = self.codes.get('account', 'pass')
        self.page.get_by_placeholder('Username').fill(login)
        self.page.get_by_placeholder('Password').fill(password)
        self.page.get_by_role("button", name="Sign in").click()
        self.page.wait_for_load_state('load', timeout=60000)
        if self._is_main_page():
            self._save_cookies()
            return True
        elif self._is_verification_page():
            try:
                self.page.locator("input[name=\"mfaForm\\:mfaCode\"]").click()
                verification_code = self.get_verification_code()
                if verification_code is None:
                    return False
                self.page.locator("input[name=\"mfaForm\\:mfaCode\"]").fill(verification_code)
                self.page.get_by_role("button", name="Submit").click()
                self.page.wait_for_load_state('load')
                self._save_cookies()
                return True
            except:
                self._save_cookies()
                return False
        else:
            return False
        
    
    def _save_cookies(self):
        time.sleep(5)
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
        
    def get_verification_code(self):
        print('[Downloader][AXA] Wait verification...')
        #logger.info('[Downloader][AXA] Wait verification...')
        mail = imaplib.IMAP4_SSL(self.codes.get("email", "imap"))
        mail.login(self.codes.get("email", "username"), self.codes.get("email", "pass"))
        mail.select("inbox")
        
        time_threshold = datetime.now() - timedelta(minutes=62) # 2
        time_threshold_str = time_threshold.strftime("%d-%b-%Y")
        found = False
        start_time = time.time()
        verification_code = None

        while not found:
            self.page.wait_for_timeout(1000)
            # Search for emails sent after the specified time
            status, messages = mail.search(None, f'(SINCE "{time_threshold_str}")')
            mail_ids = messages[0].split()
            if time.time() - start_time >= 180:
                print('[Downloader][AXA] Downloading failed due to verification timeout.')
                #logger.info('[Downloader][AXA] Downloading failed due to server connection.')
                break

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
        return result
       
    def get_all_cars(self):
        start_time = time.time()
        while len(self.car_infos) == 0:
            self.page.wait_for_timeout(1000)
            if time.time() - start_time >= 180:
                print('[Downloader][AXA] Downloading failed due to server connection.')
                #logger.info('[Downloader][AXA] Downloading failed due to server connection.')
                break
        for car_info in self.car_infos:
            if not self.update_needed(car_info):
                continue
            self.get_car_data(car_info)
                    
    def download_image(self, url, save_path):
        try:
            response = requests.get(url, headers={'Accept':'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'})
            if response.status_code == 200:
                with open(save_path, 'wb') as file:
                    file.write(response.content)
                return True
            else:
                return False
        except Exception as e:
            return False
        
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
    
    def get_car_data(self, car_info):
        for i in range(5):
            car_data = self._get_car_data(car_info)
            if car_data and self._check_car_images(car_data):
                self.save_car_json(car_data)
                return
        print(f"[Downloader][ALLIANZ][{car_info['provider_id']}] The auction downloading is failed due to error")
        return
    
    def _get_car_data(self, car_info):
        try:
            ret_car = dict()
            ret_car['title'] = car_info['title']
            ret_car['start_date'] = None
            ret_car['end_date'] = car_info['end_date'].strftime("%Y-%m-%d %H:%M:%S")
            ret_car['provider_name'] = 'axa'
            ret_car['provider_id'] = car_info['provider_id']
            ret_car['brand_name'] = car_info['title'].strip().split(' ')[0]
            ret_car['run'] = car_info['run']
            ret_car['production_date'] =  car_info['production_date'].strftime("%Y-%m-%d")
            ret_car['images_count'] = 0
            ret_car['images'] = list()
            car_data = {}
            # self.page.locator(f'[data-id="{car_id}"]').get_by_role('img').click()
            self.page.goto(car_info['url'], timeout=90000)
            self.page.wait_for_load_state('load', timeout=90000)
            self.page.wait_for_selector('#slider')
            for image_element in self.page.locator("#slider").get_by_role("listitem").all():
                image_id = image_element.get_attribute("data-id")
                if image_id:
                    ret_car['images_count'] += 1
                    ret_car["images"].append(f"{image_id}.jpg")
            # Extract extra info
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
            rows = self.page.locator('#state').locator('tr')
            for row in rows.all():
                cells = row.locator('td').all()
                if (len(cells) >= 2):
                    key = cells[0].text_content()
                    value = cells[1].text_content()
                    car_data[key] = value
            
            car_data['Sonderausstattung'] = self.page.locator("#special").text_content()
            car_data['Serienausstattung'] = self.page.locator("#serien").text_content()
            car_data['Beschädigungen'] = self.page.locator("#damage").text_content()
            car_data['Vorschaden'] = self.page.locator("#preDamagesPart").text_content()
            car_data['Brauchbare Teile'] = self.page.locator("#usablePart").text_content()
            car_data['Zusatzinformationen'] = self.page.locator("#addinfo").text_content()
            ret_car['data'] = car_data
            return ret_car
        except Exception as e:
            return None
            
    def _is_main_page(self):
        try:
            expect(self.page.locator("#myaxaId")).to_be_visible(timeout=10000)
            return True
        except AssertionError:
            return False
    
    def _is_verification_page(self):
        try:
            expect(self.page.locator("#mfaDialog")).to_be_visible(timeout=10000)
            return True
        except AssertionError:
            return False
    
    def _download_cars(self, route):
        try:
            response = route.fetch()
            req_json = response.json()
            current_datetime = datetime.now() + timedelta(seconds=10)
            for entry in req_json['list']:
                car = dict()
                car['title'] = entry.get('at', 'Unknown')
                car['provider_id'] = entry.get('a', 0)
                if entry.get('edt', None) is None:
                    car['end_date'] = (current_datetime + timedelta(seconds=entry.get('et', 0))).replace(second=0)
                else:
                    car['end_date'] = datetime.strptime(entry.get('edt', '').replace(' ', ''), "%d.%m.%Y-%H:%M")
                car['production_date'] = datetime.strptime(entry.get('r', '01/1997'), "%m/%Y")
                car['url'] = f"https://carauction.axa.ch/{entry.get('au', '')}"
                car['run'] = entry.get('km', 0)
                self.car_infos.append(car)
            route.fulfill(response=response, json=req_json)
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
        #logger.info('[Downloader][AXA] Start downloading...')
        print('[Downloader][AXA] Start downloading...')
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=False,
                # proxy={
                #     "server": self.codes.get("proxy", "server"),
                #     "username": self.codes.get("proxy", "username"),
                #     "password": self.codes.get("proxy", "password")
                # }
            )
            self.context = self.browser.new_context()
            self.context.route("**/*.{png,jpg,jpeg}", lambda route: route.abort())
            self.context.route("https://carauction.axa.ch/javax.faces.resource/dynamiccontent.properties.html?*", self._download_images)
            self.context.route("https://carauction.axa.ch/auction/list/DE", self._download_cars)
            self._load_cookies()
            self.page = self.context.new_page()
            self.page.goto(MAIN_URL, timeout=60000)
            self.page.wait_for_load_state('load')
            if not self._is_main_page():
                #logger.info('[Downloader][AXA] Sign in...')
                print('[Downloader][AXA] Sign in...')
                if not self._login():
                    #logger.info('[Downloader][AXA] Failed due to Sign in... : AXA Server Error')
                    print('[Downloader][AXA] Failed due to Sign in... : AXA Server Error')
                    return
            self.get_all_cars()
            #logger.info('[Downloader][AXA] Finish downloading')
            print('[Downloader][AXA] Finish downloading')
        except Exception as e:
            #logger.error('[Downloader][AXA] Downloading failed due to ', e)
            print('[Downloader][AXA] Downloading failed due to ', e)
            return
        self.context.close()
        self.browser.close()
    
    def update_needed(self, car):
        try:
            is_updated = True
            car_json = self.get_car_json(car)
            if car_json:
                date1 = datetime.strptime(car_json['end_date'], "%Y-%m-%d %H:%M:%S")
                date2 = car['end_date']
                time_diff = date2 - date1
                seconds_diff = time_diff.total_seconds()
                if seconds_diff > -100 and seconds_diff < 100:
                    print(f"[Downloader][AXA][{car['provider_id']}] The auction was already downloaded - cancelling...")
                    #logger.info(f"[Downloader][AXA][{car['provider_id']}] The auction was already downloaded - cancelling...")
                    is_updated = False
                else:
                    print(f"[Downloader][AXA][{car['provider_id']}] The auction was updated from {date1.strftime('%Y-%m-%d %H:%M')} to {date2.strftime('%Y-%m-%d %H:%M')}")
                    #logger.info(f"[Downloader][AXA][{car['provider_id']}] The auction was updated from {date1.strftime('%Y-%m-%d %H:%M')} to {date2.strftime('%Y-%m-%d %H:%M')}")
            else:
                print(f"[Downloader][AXA][{car['provider_id']}] New auction is downloaded")
                #logger.info(f"[Downloader][AXA][{car['provider_id']}] New auction is downloaded")
            return is_updated
        except Exception as e:
            print(f"[Downloader][AXA][{car['provider_id']}] Auction checking is failed - {str(e)}")
            #logger.info(f"[Downloader][AXA][{car['provider_id']}] Auction checking is failed - {str(e)}")
            capture_exception(e)
            return True
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


def main():
    extractor = AxaExtractor('../extracted', '../codes/axa.codes')
    extractor.get_data()
    
if __name__ == "__main__":
    main()