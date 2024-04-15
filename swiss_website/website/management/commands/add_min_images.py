import traceback
import re
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import Auction, AuctionPhoto

from django.conf import settings
from django.core.files import File
from rest_api.models import Auction, Bet

from PIL import Image


class Command(BaseCommand):
    help = 'Remove old photos'

    def handle(self, *args, **options):
        auctions = Auction.objects.filter(end_date__lte=datetime.now())    # CHANGE THIS FILTER TO USE IT PROPERLY
        for auction in auctions:
            self.add_min_photo(auction)
            print(auction)
            print(auction.min_image)

    def add_min_photo(self, auction):
        images = auction.photos_list()
        try:
            first_photo = images[0].image
        except:
            traceback.print_exc()
            return

        try:
            image = Image.open(first_photo)
            max_width = 200
            w_scale = image.size[0] / max_width
            height = image.size[1] / w_scale
            result = image.resize((int(max_width), int(height)), Image.ANTIALIAS)
            auction_id = auction.provider_id + auction.brand.name
            #result_path = os.path.join('/web_apps/swiss_website/auction_photos/', str(auction_id)+'.png')
            result_path = os.path.join('/web_apps/swiss_website/auction_photos/', str(auction_id)+'.jpg')
            result.save(result_path, format='JPEG')

            with open(result_path, 'rb') as f:
                auction.min_image = File(f)
                auction.save()
        except:
            auction.min_image = first_photo
            auction.save()
            traceback.print_exc()
