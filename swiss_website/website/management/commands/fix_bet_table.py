from django.core.management.base import BaseCommand, CommandError

from rest_api.models import Auction, Bet, UserPrivate, TopBet, ScheduledBet
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Fix bets table'
    def handle(self, *args, **options):
        ### update bet with auction
        bets = Bet.objects.all().order_by('id').select_related('auction')
        for bet in bets:
            bet.auction_end_date = bet.auction.end_date
            bet.save()
            print(f"@@@ BET: {bet.id}")
        ### update topbet table with bet
        top_bet_ids = Bet.objects.all().order_by('auction', '-price').distinct('auction')
        top_bets = Bet.objects.filter(id__in=top_bet_ids).order_by('id').select_related('auction')
        for bet in top_bets:
            try:
                user = UserPrivate.objects.get(user=bet.user)
            except UserPrivate.DoesNotExist as e:
                print(bet.id, ":invalid user")
                continue
            topbet, created = TopBet.objects.get_or_create(auction=bet.auction)
            bet_count = Bet.objects.filter(auction=bet.auction).count()
            topbet.bet_count = bet_count
            topbet.auction_end_date = bet.auction.end_date
            topbet.user = user
            topbet.bet = bet
            topbet.price = bet.price
            topbet.color = bet.color
            topbet.scheduled = ScheduledBet.objects.filter(bet=bet).exists()
            topbet.save()
            print(f"### TOPBET : {topbet.id} : {bet.auction.id} : {bet_count}")
        ### update scheduled bets
        scheduled_bets = ScheduledBet.objects.all().order_by('id')
        for scheduledbet in scheduled_bets:
            try:
                topbet = TopBet.objects.get(bet=scheduledbet.bet)
                print('### : ', scheduledbet.id, topbet.id)
                scheduledbet.topbet = topbet
                scheduledbet.save()
            except TopBet.DoesNotExist as e:
                print(f'$$$ SCHBET: ', bet.id)
