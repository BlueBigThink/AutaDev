import traceback
import json
import re
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib.admin.models import LogEntry
from rest_api.models import Auction, AuctionUserFile, Bet
from web_app.utils import log_exception

from django.conf import settings


class Command(BaseCommand):
    help = 'Removes old user files'

    def handle(self, *args, **options):
        user_files = AuctionUserFile.objects.all().order_by('-auction__end_date')
        for uf in user_files:
            now = datetime.now()
            date_threshold = now - timedelta(days=60)
            auction = uf.auction
            try:
                highest_won_bet = Bet.objects.get(auction=auction, color=1)
                content_type = ContentType.objects.get_for_model(Bet)
                log = LogEntry.objects.filter(content_type=content_type, object_id=str(highest_won_bet.id)).order_by('-action_time').first()
                if log.action_time > date_threshold:
                    continue
                os.remove(uf.uploaded.path)
                uf.delete()
            except Exception as e:
                log_exception(e)
