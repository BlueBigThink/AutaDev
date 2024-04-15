import re
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import Auction, AuctionPhoto

from django.conf import settings
from rest_api.models import Auction, Bet


class Command(BaseCommand):
    help = 'Removes photos older than 90 days for not won auctions'

    def handle(self, *args, **options):
        self.remove_photos_older_than_90days()

    def remove_photos_older_than_90days(self):
        now = datetime.now()
        date_threshold = now - timedelta(days=90)
        auctions = Auction.objects.filter(end_date__lt=date_threshold)

        for auction in auctions:
            bets = Bet.objects.filter(auction=auction, color__in=[1, 2])
            if len(bets) != 0:
                continue
            self.delete_auction_photos_leaving_3(auction)

    def delete_auction_photos_leaving_3(self, auction):
        photos = auction.photos_list()[5:]
        for photo in photos:
            no_logo_path = self.get_no_logo_path(photo.image.path)
            try:
                os.remove(no_logo_path)
            except:
                pass
            try:
                os.remove(photo.image.path)
            except:
                pass
            photo.delete()

    def get_no_logo_path(self, filename):
        a = filename
        b = a.split('.')[:-1]
        b = '.'.join(b)
        c = a.split('.')[-1]
        no_logo_path = b + '_no_logo.' + c
        return no_logo_path
