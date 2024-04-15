import logging
import threading
import traceback
import time
import re
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import Auction, Auction
from web_app.utils import log_exception

from django.conf import settings
from rest_api.models import Auction, Bet, ScheduledBet

from .bet_controllers.rest_bet_controller import RestBetController
from .bet_controllers.scc_bet_controller import SccBetController

INTERVAL = 5
WORKER_START = 60
SCHEDULED_BUSY_SECS = 50
CONTROLLERS = {
    'rest': RestBetController,
    # 'scc': SccBetController,
}
LOGIN_LOCK = threading.Lock()

logger = logging.getLogger(__name__)

print('start')

def do_bet(controller, bet_scheduled):
    auction = bet_scheduled.bet.auction
    logger.info('[Bet][%s][%s] Betting started - %sCHF, %s' % (auction.provider_name.upper(), auction.provider_id, bet_scheduled.price, bet_scheduled.price_max))
    try:
        price = int(bet_scheduled.price)
        price_max = int(bet_scheduled.price_max)
        logger.info(controller.session.cookies.get_dict())
        controller.bet(auction, price, price_max, bet_scheduled.is_aggressive)
        bet_scheduled.betted = True
        bet_scheduled.save()
        logger.info('[Bet][%s][%s] Betting finished - %sCHF, %sCHF' % (auction.provider_name.upper(), auction.provider_id, price, price_max))
    except Exception as e:
        log_exception(e)
        bet_scheduled.betted = False
        bet_scheduled.save()


def do_login_and_schedule_bet(auction, bet_scheduled):
    try:
        cur_controller = CONTROLLERS[auction.provider_name](auction)
    except KeyError as e:
        log_exception(e)

    try:
        if auction.provider_name == 'scc':
            logger.info('[Bet][%s][%s] Betting lock acquired' % (auction.provider_name.upper(), auction.provider_id))
            LOGIN_LOCK.acquire()
        logger.info('[Bet][%s][%s] Betting login started' % (auction.provider_name.upper(), auction.provider_id))
        cur_controller.login()
        if auction.provider_name == 'scc':
            logger.info('[Bet][%s][%s] Betting lock released' % (auction.provider_name.upper(), auction.provider_id))
            LOGIN_LOCK.release()
    except Exception as e:
        log_exception(e)
        if auction.provider_name == 'scc':
            logger.warning('[Bet][%s][%s] Betting lock released' % (auction.provider_name.upper(), auction.provider_id))
            LOGIN_LOCK.release()
        return

    try:
        logger.info('[Bet][%s][%s] Betting prepare started' % (auction.provider_name.upper(), auction.provider_id))
        cur_controller.prepare()
    except Exception as e:
        log_exception(e)
        return

    now = datetime.now()

    if auction.provider_name == 'rest':
        time_to_wait = (auction.end_date - now - timedelta(seconds=6)).total_seconds()
        bet_worker = threading.Timer(time_to_wait, do_bet, (cur_controller, bet_scheduled))
        bet_worker.start()

        time_to_wait = (auction.end_date - now - timedelta(seconds=2.0)).total_seconds()
        bet_worker = threading.Timer(time_to_wait, do_bet, (cur_controller, bet_scheduled))
        bet_worker.start()

        time_to_wait = (auction.end_date - now - timedelta(seconds=1.5)).total_seconds()
        bet_worker = threading.Timer(time_to_wait, do_bet, (cur_controller, bet_scheduled))
        bet_worker.start()

        time_to_wait = (auction.end_date - now - timedelta(seconds=1.0)).total_seconds()
        bet_worker = threading.Timer(time_to_wait, do_bet, (cur_controller, bet_scheduled))
        bet_worker.start()

        time_to_wait = (auction.end_date - now - timedelta(seconds=0.5)).total_seconds()
        bet_worker = threading.Timer(time_to_wait, do_bet, (cur_controller, bet_scheduled))
        bet_worker.start()

        time_to_wait = (auction.end_date - now - timedelta(seconds=0.4)).total_seconds()
        bet_worker = threading.Timer(time_to_wait, do_bet, (cur_controller, bet_scheduled))
        bet_worker.start()

        time_to_wait = (auction.end_date - now - timedelta(seconds=0.2)).total_seconds()
        bet_worker = threading.Timer(time_to_wait, do_bet, (cur_controller, bet_scheduled))
        bet_worker.start()
    elif auction.provider_name == 'scc':
        # multiply similar to rest if connection error occurs
        time_to_wait = (auction.end_date - now - timedelta(seconds=4)).total_seconds()
        bet_worker = threading.Timer(time_to_wait, do_bet, (cur_controller, bet_scheduled))
        bet_worker.start()

    bet_scheduled.scheduled = True
    bet_scheduled.save()
    logger.info('[Bet][%s][%s] Betting scheduled in %s' % (auction.provider_name.upper(), auction.provider_id, time_to_wait))


class Command(BaseCommand):
    help = 'Bets automatically - must be running in background'

    def handle(self, *args, **options):
        scheduled_recently = list()

        while True:
            now = datetime.now()
            # find scheduled bets which auction end date is not reached and schedules flag is false
            bets_scheduled = ScheduledBet.objects.filter(bet__auction__end_date__gt=now, scheduled=False)
            scheduled_recently = [s for s in scheduled_recently if s['time'] + timedelta(seconds=SCHEDULED_BUSY_SECS) > now]
            for bet_scheduled in bets_scheduled:
                auction = bet_scheduled.bet.auction
                if any(s['pk'] == bet_scheduled.pk for s in scheduled_recently):
                    logger.info('[Bet][%s][%s] Worker waits - betting scheduled recently' % (auction.provider_name.upper(), auction.provider_id))
                    continue

                now = datetime.now()
                if now > self.date_offset(bet_scheduled.bet.auction.end_date):
                    worker = threading.Timer(0.1, do_login_and_schedule_bet, (auction, bet_scheduled))
                    worker.start()
                    logger.info('[Bet][%s][%s] Worker started' % (auction.provider_name.upper(), auction.provider_id))
                    scheduled_recently.append({"pk": bet_scheduled.pk, "time": now})
                    logger.info('[Bet][%s][%s] Scheduled_recently appended' % (auction.provider_name.upper(), auction.provider_id))

            time.sleep(INTERVAL)

    # get the time 30 seconds before target_date
    def date_offset(self, target_date):
        return target_date - timedelta(seconds=WORKER_START)
