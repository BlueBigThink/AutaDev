import re
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import Auction, AuctionPhoto

from django.conf import settings
from rest_api.models import Auction, Bet, UserPrivate
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
import json


class Command(BaseCommand):
    help = 'Restore removed bets'

    def handle(self, *args, **options):
        #self.color_changed()
        #self.added()
        self.note_changed()

    def add_bet(self, user, auction, price):
        auction = auction[0]
        if auction.provider_name not in ["rest", "axa"]:
            return
        bets = Bet.objects.filter(user=user, auction=auction, price=price)
        if len(bets) > 0:
            #print('Istnieje')
            return
        b = Bet(user=user, auction=auction, price=price, date=auction.end_date-timedelta(hours=1))
        b.save()
        print('Dodano')
        print("%s %s %s %s" % (user, price, auction, auction.provider_id))

    def note_changed(self):
        entries = LogEntry.objects.filter(user__id__in=[27, 263], content_type__id__exact=16, action_time__gte=datetime(2020, 5, 11, 11, 0, 0, 0))
        count1 = 0
        count2 = 0
        count3 = 0
        for entry in entries:
            #print(entry.object_repr)
            #print(entry.change_message)
            if not entry.change_message or len(json.loads(entry.change_message)) == 0:
                continue
            if 'changed' not in json.loads(entry.change_message)[0]:
                continue
            if 'note' not in json.loads(entry.change_message)[0]['changed']['fields']:
                continue
            email = entry.object_repr.split(' - ')[0].strip()
            user = User.objects.get(email=email)

            price = int(entry.object_repr.split('-')[-1].replace('CHF', '').strip())

            auction_title = ''.join(entry.object_repr.split(' - ')[1:-1]).strip()
            timedelta_time1 = entry.action_time + timedelta(days=3)
            timedelta_time2 = entry.action_time - timedelta(days=3)
            auction = Auction.objects.filter(title=auction_title, end_date__lte=timedelta_time1, end_date__gte=timedelta_time2)
            if len(auction) > 1:
                count1 += 1
            elif len(auction) == 0:
                count2 += 1
            else:
                self.add_bet(user, auction, price)
                count3 += 1

            #print("%s %s %s" % (email, price, auction))

        #print(count1)
        #print(count2)
        #print(count3)

    def added(self):
        entries = LogEntry.objects.filter(user__id__in=[27, 263], content_type__id__exact=16, action_time__gte=datetime(2020, 5, 11, 11, 0, 0, 0))
        count1 = 0
        count2 = 0
        count3 = 0
        for entry in entries:
            #print(entry.object_repr)
            #print(entry.change_message)
            if not entry.change_message or len(json.loads(entry.change_message)) == 0:
                continue
            if 'added' not in json.loads(entry.change_message)[0]:
                continue
            email = entry.object_repr.split(' - ')[0].strip()
            user = User.objects.get(email=email)

            price = int(entry.object_repr.split('-')[-1].replace('CHF', '').strip())

            auction_title = ''.join(entry.object_repr.split(' - ')[1:-1]).strip()
            auction = Auction.objects.filter(title=auction_title, end_date__gte=datetime(2020, 4, 11, 11, 0, 0, 0))
            if len(auction) > 1:
                count1 += 1
            elif len(auction) == 0:
                count2 += 1
            else:
                self.add_bet(user, auction, price)
                count3 += 1

            print("%s %s %s" % (email, price, auction))

        print(count1)
        print(count2)
        print(count3)

    def color_changed(self):
        entries = LogEntry.objects.filter(user__id__in=[27, 263], content_type__id__exact=16, action_time__gte=datetime(2020, 5, 11, 11, 0, 0, 0))
        count1 = 0
        count2 = 0
        count3 = 0
        for entry in entries:
            #print(entry.object_repr)
            #print(entry.change_message)
            if not entry.change_message or len(json.loads(entry.change_message)) == 0:
                continue
            if 'changed' not in json.loads(entry.change_message)[0]:
                continue
            if json.loads(entry.change_message)[0]['changed']['fields'] != ['color']:
                continue
            email = entry.object_repr.split(' - ')[0].strip()
            user = User.objects.get(email=email)

            price = int(entry.object_repr.split('-')[-1].replace('CHF', '').strip())

            auction_title = ''.join(entry.object_repr.split(' - ')[1:-1]).strip()
            auction = Auction.objects.filter(title=auction_title, end_date__gte=datetime(2020, 4, 11, 11, 0, 0, 0))
            #print(auction)
            if len(auction) > 1:
                count1 += 1
            elif len(auction) == 0:
                count2 += 1
            else:
                self.add_bet(user, auction, price)
                count3 += 1

            #print("%s %s %s" % (email, price, auction))

        #print(count1)
        #print(count2)
        #print(count3)
