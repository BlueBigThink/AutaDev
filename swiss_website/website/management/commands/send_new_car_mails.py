import logging
import re
from django.core.mail import send_mail, BadHeaderError
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import Auction, WatchTag, UserPrivate, UserBusiness

from web_app.language_manager import LanguageManager
from web_app.utils import log_exception
from django.conf import settings
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sends emails to users about new auctions'

    def handle(self, *args, **options):
        now = datetime.now()
        time_threshold = now - timedelta(hours=24)

        auctions = Auction.objects.filter(Q(added_time__gt=time_threshold) & Q(end_date__gte=now) & Q(published=True))
        # auctions = list(auctions)
        private_users = UserPrivate.objects.all()
        business_users = UserBusiness.objects.all()
        users = list(private_users) + list(business_users)

        for user in users:
            user_auctions = list()
            users_watch = WatchTag.objects.filter(user=user.user)

            for watch in users_watch:
                tag_auctions = auctions.filter(title__icontains=watch.tag)
                tag_auctions = set(tag_auctions) - set(user_auctions)
                user_auctions += list(tag_auctions)

            if len(user_auctions) > 0:
                self.send_email(user, user_auctions)

    def send_email(self, user, auctions):
        language_manager = LanguageManager()
        subject = language_manager.get_trans(user.user, 'email-6')
        message = '{} {},<br/><br/>'.format(language_manager.get_trans(user.user, 'email-7'), user.first_name)
        message += '%s <br/><br/>' % (language_manager.get_trans(user.user, 'email-8'))

        for auction in auctions:
            link = 'http://autazeszwajcarii.pl/aukcje/licytacja/{}/{}'.format(
                auction.id,
                re.sub('[^0-9a-zA-Z]+', '-', auction.title.lower())
            )
            auction_str = '<a href="{}">{}</a><br/>'.format(link, auction.title)
            message += auction_str

        message += '<br/><br/>%s<br/>' % (language_manager.get_trans(user.user, 'email-9'))
        message += language_manager.get_trans(user.user, 'email-10')
        message += '<br/><br/>%s<br/>%s' % (language_manager.get_trans(user.user, 'email-11'), language_manager.get_trans(user.user, 'email-12'))

        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_NORESPONSE,
                [user.user.email],
                html_message=message,
                fail_silently=False,
            )
            logger.info('Sent email from %s to %s, subject: %s, cars number: %s' % (settings.EMAIL_NORESPONSE, user.user.email, subject, len(auctions)))
        except Exception as e:
            log_exception(e)