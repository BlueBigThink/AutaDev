from django.core.management.base import BaseCommand, CommandError

from rest_api.models import Auction, Bet, UserPrivate, TopBet, ScheduledBet
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Fix bets table'

    def _process_bet(self, scheduledbet):
        try:
            topbet = TopBet.objects.get(bet=scheduledbet.bet)
            print('### : ', scheduledbet.id, topbet.id)
            scheduledbet.topbet = topbet
            scheduledbet.save()
        except TopBet.DoesNotExist as e:
           print('### : ', scheduledbet.id)
#            scheduledbet.delete()
    
    def handle(self, *args, **options):
        bets = ScheduledBet.objects.all()
        print('---Process Scheduled Bet')
        for bet in bets:
            self._process_bet(bet)
            
