import re
from django.core.mail import send_mail, BadHeaderError
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import Auction, WatchTag, UserPrivate, UserBusiness

from web_app.language_manager import LanguageManager
from django.conf import settings


class Command(BaseCommand):
    help = 'Sends emails to users about new auctions'

    def handle(self, *args, **options):
        send_mail(
            "bbb",
            "aaaa",
            settings.EMAIL_NORESPONSE,
            ['jstemplewski@gmail.com'],
            html_message="aaaaa",
        )
