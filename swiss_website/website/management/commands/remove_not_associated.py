import logging
import traceback
import json
import re
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import Auction, AuctionPhoto

from django.conf import settings
from rest_api.models import Auction, Bet
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Removes not associated old files'

    def handle(self, *args, **options):
        auctions = Auction.objects.all()
        paths = list()
        count = 0
        for auction in auctions:
            photos = auction.photos_list()
            for photo in photos:
                path = photo.image.path
                paths.append(path)

                # add no_logo below
                no_logo_path = self.get_no_logo_path(path)
                paths.append(no_logo_path)
            try:
                paths.append(auction.min_image.path)
            except:
                pass
            count += 1

        directory = '/web_apps/swiss_website/auction_photos/'
        existing_paths = list()
        for filename in os.listdir(directory):
            full_path = directory + filename
            existing_paths.append(full_path)

        diff = set(existing_paths) - set(paths)

        # saving 
        diff_json = {'files': list(diff)}
        with open('/tmp/diff.json', 'w') as f:
            json.dump(diff_json, f)

        # remove diff here
        for to_rm in diff:
            try:
                os.remove(to_rm)
            except:
                print(to_rm)

    def get_no_logo_path(self, filename):
        a = filename
        b = a.split('.')[:-1]
        b = '.'.join(b)
        c = a.split('.')[-1]
        no_logo_path = b + '_no_logo.' + c
        return no_logo_path
