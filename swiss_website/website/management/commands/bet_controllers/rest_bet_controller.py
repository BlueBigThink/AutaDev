import hashlib
import logging
from configparser import ConfigParser
import requests
from lxml import html
from .bet_controller import BetController
from web_app.utils import log_exception
logger = logging.getLogger(__name__)


LOGIN_URL = 'https://www.restwertboerse.ch/index.php'
BET_URL = 'https://www.restwertboerse.ch/offer-detail.php'
CODES_FILE = '/web_apps/app_download/codes/rest.codes'

class RestBetController(BetController):
    def __init__(self, auction):
        self.codes = ConfigParser()
        self.codes.read(CODES_FILE)
        self.session = requests.Session()
        self.auction = auction
    
    def bet(self, auction_obj, price, price_max=None, is_aggressive=False):
        url_params = {'id': auction_obj.provider_id}
        auction_request = self.session.get(BET_URL, params=url_params)
        doc = html.fromstring(auction_request.content)
        current_price = 0
        try:
            price_text = doc.xpath("//p[@class='form-control-static']/b")[0].text
            current_price = int(float(price_text.replace('CHF ', '').replace('\'', '')))
        except:
            current_price = 0
        logger.info("[BetAutomate][REST][%s] Current price is %s CHF" % (auction_obj.provider_id, current_price))

        price_to_bet = 0
        if current_price == 0:
            price_to_bet = price
        elif current_price % 10 == 5 and (current_price + 200) <= price_max:
            price_to_bet = max(current_price - 5 + 200 + 6, price)
        elif current_price % 10 == 5:
            price_to_bet = 0
        elif current_price < price:
            price_to_bet = price
        elif current_price % 10 != 6 and (current_price - current_price % 10 + 6) <= price_max and (current_price - current_price % 10 + 6) > current_price:
            price_to_bet = current_price - current_price % 10 + 6
        elif current_price % 10 != 6 and (current_price - current_price % 10 + 10 + 6) <= price_max and (current_price - current_price % 10 + 10 + 6) > current_price:
            price_to_bet = current_price - current_price % 10 + 10 + 6

        logger.info("[BetAutomate][REST][%s] Price to bet is set to %s CHF" % (auction_obj.provider_id, price_to_bet))
        if price_to_bet == 0:
            logger.info("[BetAutomate][REST][%s] Bet is cancelled" % auction_obj.provider_id)
            return

        data = {
            'action': 'add_bid',
            'id': auction_obj.provider_id,
            'ac': '',
            'm': '',
            'q': '',
            'page': '',
            'amount1': int(price_to_bet)
        }
        ret = self.session.post(BET_URL, data=data)
        logger.info("[BetAutomate][REST][%s] Bet is sent - %s CHF" % (auction_obj.provider_id, price_to_bet))

    def logout(self):
        self.session.cookies.clear()

    def login(self):
        login = self.codes.get('account', 'login')
        password = self.codes.get('account', 'pass')
        m = hashlib.sha512()
        m.update(password.encode('utf-8'))
        hashed_pass = m.hexdigest()

        data = {
            'p1': hashed_pass,
            'username': login,
            'action': 'login',
            'ref': '',
            'agb': '1',
        }

        self.session.post(LOGIN_URL, data=data)

    def prepare(self):
        pass
'''
POST /offer-detail.php HTTP/1.1
Host: www.restwertboerse.ch
User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:69.0) Gecko/20100101 Firefox/69.0
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
Content-Type: application/x-www-form-urlencoded
Content-Length: 51
Connection: close
Referer: https://www.restwertboerse.ch/offer-detail?id=238713&page=2
Cookie: _ga=GA1.2.801406313.1564505880; rwbsessionid=ugqnjts811v265m6dn0ceqg9a0
Upgrade-Insecure-Requests: 1
Pragma: no-cache
Cache-Control: no-cache

action=add_bid&id=238713&ac=&m=&q=&page=2&amount1=6
'''
