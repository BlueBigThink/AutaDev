import logging
import re
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import Auction, Auction

from django.conf import settings
from rest_api.models import Auction, Bet
from twilio.rest import Client
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Send SMS for bets'

    def handle(self, *args, **options):
        now = datetime.now()
        delta = timedelta(minutes=10)
        later = now + delta
        bets = Bet.objects.filter(auction__end_date__range=(now, later), sms_sent=False, betted=False)
        for bet in bets:
            auction_title = bet.auction.title
            delta = bet.auction.end_date - now
            time_to_end = "%d minut i %d sekund" % (delta.seconds//60,  delta.seconds%60)
            self.send_sms(auction_title, time_to_end) 
            bet.sms_sent = True
            bet.save()

    def send_sms(self, auction_name, time_to_end):
        body = "Pojawiła się nowa licytacja. %s do zakończenia. %s" % (time_to_end, auction_name)
        auth_token = ''
        account_sid = ''
        client = Client(account_sid, auth_token)
        from_num = ''
        to_num = ''
        message = client.messages.create(body=body, from_=from_num, to=to_num)
        logger.info('Sent SMS from %s to %s, message:' % (from_num, to_num, message[:20]))