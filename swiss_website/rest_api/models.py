from functools import cmp_to_key

from urllib.parse import quote
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.db import models
from django.db.models.signals import post_save, post_delete, pre_delete, pre_save
from django.db.models import Q
from django.contrib.postgres.fields import JSONField
from django.contrib.auth.models import User
from django.utils import timezone
from web_app.settings import WEBSOCKET_HOST, WEBSOCKET_PORT
from web_app.utils import log_exception
from django.conf import settings

import os
import json
import random
import string
import re
import logging
logger = logging.getLogger(__name__)

from twilio.rest import Client


class Brand(models.Model):
    name = models.CharField(max_length=63)

    def __str__(self):
        return self.name


class LanguageModel(models.Model):
    class Meta:
        verbose_name = 'Języki'
        verbose_name_plural = 'Języki'
        app_label = 'rest_api'


class BetNotificationsModel(models.Model):
    phone_number = models.CharField(max_length=64, blank=False, null=False, verbose_name='Nr telefonu')
    activated = models.BooleanField(default=False, verbose_name='Aktywowany')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='Data zakończenia')

    class Meta:
        verbose_name = 'Powiadomienia SMS'
        verbose_name_plural = 'Powiadomienia SMS'
        app_label = 'rest_api'


class AutomateDashboardModel(models.Model):
    class Meta:
        verbose_name = 'Panel Zarządzania Automatyzacją'
        verbose_name_plural = 'Panel Zarządzania Automatyzacją'
        app_label = 'rest_api'


class ShortUrlModel(models.Model):
    title = models.CharField(max_length=64, blank=False, null=False, verbose_name='Tytuł')
    url = models.CharField(max_length=2000, blank=False, null=False, verbose_name='URL')
    short_url = models.CharField(max_length=40, blank=False, null=False, verbose_name='Krótki URL')

    class Meta:
        verbose_name = 'Krótkie linki'
        verbose_name_plural = 'Krótkie linki'
        app_label = 'rest_api'

    def __str__(self):
        return self.title

class MarketingCampaign(models.Model):
    name = models.CharField(max_length=63, verbose_name='Nazwa kampani')
    cookie_value = models.CharField(max_length=63, verbose_name='Wartość Cookiesa')
    url_string = models.CharField(max_length=63, verbose_name='Fragment referencyjnego URL lub Referer')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Kampania Marketingowa'
        verbose_name_plural = 'Kampanie Marketingowe'

class UserPrivate(models.Model):
    def has_add_permission(self, request):
        return False

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Użytkownik',
        editable=False,
    )

    user_top = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        verbose_name='Zarządca',
        blank=True,
        null=True,
    )

    campaign_source = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.SET_NULL,
        verbose_name='Kampania źródłowa',
        blank=True,
        null=True,
    )

    # more data about user here
    accepted = models.BooleanField(default=False, verbose_name='Zaakceptowano')
    first_name = models.CharField(max_length=31, blank=True, null=True, verbose_name='Imię')
    second_name = models.CharField(max_length=31, blank=True, null=True, verbose_name='Drugie imię')
    last_name = models.CharField(max_length=63, blank=True, null=True, verbose_name='Nazwisko')
    phone_number = models.CharField(max_length=31, blank=True, null=True, verbose_name='Telefon')
    slug = models.CharField(max_length=31, blank=True, null=True, verbose_name='slug')
    note = models.TextField(null=True, blank=True, verbose_name='Notka', max_length=255)
    lang = models.CharField(max_length=3, default='pl', verbose_name='Język', choices=(
            ('pl', 'Polski'),
            ('en', 'Angielski'),
            ('ru', 'Rosyjski'),
            ('de', 'Niemiecki'),
        )
    )
    token = models.CharField(max_length=127, blank=True, null=True, verbose_name='Reset token')
    token_end_of_validity = models.DateTimeField(null=True, blank=True, verbose_name='Ważność tokena')
    country = models.CharField(max_length=63, blank=True, null=True, verbose_name='Kraj')
    postal_code = models.CharField(max_length=31, blank=True, null=True, verbose_name='Kod poczt.')
    city_name = models.CharField(max_length=31, blank=True, null=True, verbose_name='Miasto')
    street_name = models.CharField(max_length=127, blank=True, null=True, verbose_name='Ulica')
    home_number = models.CharField(max_length=63, blank=True, null=True, verbose_name='Dom/Mieszkanie')
    promocode = models.CharField(max_length=63, blank=True, null=True, verbose_name='Kod promo')
    lookup = models.CharField(max_length=255)
    calculator_enabled = models.BooleanField(default=True, verbose_name='Dostępny kalkulator')
    registered_at = models.DateTimeField(blank=True, null=True, verbose_name='Data rejestracji')

    def bets(self):
        return '<a href="/admin/rest_api/bet/?q=%s" style="color:#ac0303">%s</a>' % (self.user.email, 'Licytacje')
    bets.allow_tags = True
    bets.short_description='Licytacje'

    def email(self):
        return self.user.email
    email.shortdescription = 'Email'

    def __str__(self):
        return "{} {} ({})".format(
            self.first_name,
            self.last_name,
            self.user.email
        )
    
    def save(self, *args, **kwargs):
        self.lookup = self.__str__()
        if not self.id:
            self.registered_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Uzytkownik'
        verbose_name_plural = 'Uzytkownicy'
        indexes = [
            models.Index(fields=['id']),
        ]

class Banner(models.Model):
    title = models.CharField(max_length=127, blank=False, null=False, verbose_name='Nazwa')
    min_image = models.FileField(verbose_name='Baner', upload_to='static/website', blank=True)
    published = models.BooleanField(default=True, verbose_name='Opublikowany', db_index=True)

    class Meta:
        verbose_name = 'Baner'
        verbose_name_plural = 'Banery'

    def __str__(self):
        return self.title


class Auction(models.Model):
    title = models.CharField(max_length=127, verbose_name='Tytuł')
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='Start')
    end_date = models.DateTimeField(verbose_name='Zakończenie')
    data = JSONField(verbose_name='Dane')
    images_count = models.IntegerField(default=-1,verbose_name='Liczba zdjęć (nieważne tutaj)')
    added_time = models.DateTimeField(auto_now_add=True, verbose_name='Data dodania')
    ref_id = models.CharField(max_length=15, verbose_name='Nr ref.', blank=True, null=True)
    min_image = models.FileField(verbose_name='Male zdjecie', upload_to='auction_photos', blank=True)
    highlighted = models.BooleanField(default=False, verbose_name='Wyróżnienie')

    # below generic data for all providers
    provider_name = models.CharField(max_length=31, verbose_name='Ubezp.')
    provider_id = models.CharField(max_length=127, verbose_name='ID ubezp.')
    subprovider_name = models.CharField(max_length=127, verbose_name='Sprzedający', default='')
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        verbose_name='Marka'
    )
    published = models.BooleanField(default=True, verbose_name='Opublikowany')
    production_date = models.DateField(verbose_name='Data prod.')
    run = models.IntegerField(verbose_name='Przebieg')

    def first_photo_img(self):
        link = self.get_link()
        first = self.first_photo()
        return '<a href="%s" target="_blank"><img src="/%s" style="max-width:100px"/></a>' % (link, first,)
    first_photo_img.allow_tags = True
    first_photo_img.short_description = "Zdjęcie"

    def get_provider_link(self):
        link = '#'
        if self.provider_name == 'axa':
            ident = url_encoded = quote(self.provider_id)
            link = 'https://carauction.axa.ch/auction/car/auctiondetails.html?article={}&ref=start'.format(ident)
            try:
                if self.data['moto'] == True:
                    link = link.replace('/car/', '/moto/')
            except:
                pass
        elif self.provider_name == 'allianz':
            url_encoded = quote(self.provider_id)
            link = 'https://www.allianz-carauction.ch/auction/car/auctiondetails.html?article={}&ref=start'.format(url_encoded)
        elif self.provider_name == 'scc':
            is_old = 0
            if self.end_date < datetime.now():
                is_old = 1
            link = 'https://secure.swisscrashcars.ch/cars/#%s_%s' % (self.provider_id, is_old)
        elif self.provider_name == 'rest':
            link = 'https://www.restwertboerse.ch/offer-detail?id=%s' % self.provider_id
        
        return link

    def to_end_date(self):
        to_end = self.end_date - datetime.now()
        sign = ''
        if self.end_date < datetime.now():
            sign = '-'
            to_end = datetime.now() - self.end_date
        to_end_splitted = str(to_end).split(',')
        part2 = to_end_splitted[-1].split(':')

        if len(to_end_splitted) == 1:
            to_end_string = '%sg. %sm. %ss.' % (part2[0], part2[1], part2[2].split('.')[0])
        elif len(to_end_splitted) == 2:
            days = to_end_splitted[-2][:-4]
            to_end_string = '%sdni %sg. %sm. %ss.' % (days, part2[0], part2[1], part2[2].split('.')[0])
        elif len(to_end_splitted) == 3:
            days = to_end_splitted[-2]
            years = to_end_splitted[-3][:-6]
            to_end_string = '%slat %sdni %sg. %sm. %ss.' % (years, days, part2[0], part2[1], part2[2].split('.')[0])

        return sign+to_end_string
    to_end_date.short_description = "Do końca"

    def photos_list(self):
        return self.photos.all()

    def first_photo(self):
        photos = self.photos.all()
        return photos[0]

    def get_bets_link(self):
        return f'/admin/rest_api/bet/?q={self.ref_id}'
    
    def get_user_bets_link(self):
        return f'/admin/rest_api/bet/?q={self.user.email}'

    def get_link(self):
        link = '/aukcje/licytacja/{}/{}'.format(
            self.id,
            re.sub('[^0-9a-zA-Z]+', '-', self.title.lower())
        )
        return link
    
    def get_bets(self):
        bets_count = Bet.objects.filter(auction=self).count()
        link = '<a target="_blank" href="/admin/rest_api/bet/?q=%s">Licytacje</a><span style="color:#ac0303">(%s)</span>' % (self.ref_id, bets_count)
        return link
    get_bets.short_description = 'Licytacje'
    get_bets.allow_tags = True

    def __str__(self):
        return '%s - %s' % (self.ref_id, self.title)

    class Meta:
        verbose_name = 'Aukcja'
        verbose_name_plural = 'Aukcje'
        indexes = [
            models.Index(fields=['id']),
            models.Index(fields=['-end_date']),
            models.Index(fields=['provider_name']),
            # models.Index(fields=['-provider_id']),
            # models.Index(fields=['ref_id']),
        ]


class TopAuction(models.Model):
    auction = models.ForeignKey(
        Auction,
        related_name='auction',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Aukcja',
        limit_choices_to={'published': True, 'end_date__gte': timezone.now()},
        help_text='Można wybrać aukcję lub ustawić własne zdjęcie z własnym tytułem',
    )
    image = models.FileField(upload_to='auction_photos', null=True, blank=True, verbose_name='Zdjęcie', help_text='Nie ustawiać, gdy wyżej wybrano aukcje')
    title = models.CharField(max_length=127, blank=True, null=True, verbose_name='Tytuł', help_text='Można ustawić tytuł, nawet gdy wybrano aukcje')
    link = models.CharField(max_length=127, null=True, blank=True, verbose_name='Link', help_text='Link po kliknięciu w zdjęcie, nie ustawiać gdy wybrano aukcje')

    def get_title(self):
        if self.title or not self.auction:
            return self.title

        return self.auction.title
    get_title.short_description = 'Tytuł aukcji'

    def get_link(self):
        if self.auction:
            return self.auction.get_link()
        return link
    get_link.allow_tags = True
    get_link.short_description = "Link"
    
    def get_end_date(self):
        if self.auction:
            return self.auction.end_date
        return 'Brak zakończenia'
    get_end_date.short_description = "Data zakończenia"
    
    def get_photo_auction(self):
        if self.auction:
            return self.auction.first_photo_img()
        return 'Obraz dodany samodzielnie'
    get_photo_auction.allow_tags = True
    get_photo_auction.short_description = "Zdjęcie"

    def admin_link(self):
        if self.auction:
            return '<a href="%s" target="_blank">Link</a>' % self.auction.get_link()
        return '<a href="%s" target="_blank">Link</a>' % self.link
    admin_link.allow_tags = True
    admin_link.short_description = "Link"

    @property
    def get_photo(self):
        if self.auction:
            return self.auction.first_photo

        return self.image.name

    def __str__(self):
        return self.get_title()

    class Meta:
        verbose_name = 'Aukcja dnia'
        verbose_name_plural = 'Aukcje dnia'


class AuctionPhoto(models.Model):
    image = models.FileField(upload_to='auction_photos')
    auction = models.ForeignKey(
        Auction,
        related_name='photos',
        on_delete=models.CASCADE,
    )

    @property
    def name(self):
        return self.image.name

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Zdjecie aukcji'
        verbose_name_plural = 'Zdjecia aukcji'


class WatchTag(models.Model):
    tag = models.CharField(max_length=127)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )


class WatchAuction(models.Model):
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

   
class Bet(models.Model):
    accepted = models.BooleanField(verbose_name='Zaakceptowano', default=True)
    price = models.IntegerField(verbose_name='Cena [CHF]')
    date = models.DateTimeField(verbose_name='Data wbicia', auto_now_add=True)
    sms_sent = models.BooleanField(verbose_name='Wyslano SMS', default=False)
    betted = models.BooleanField(verbose_name='Wbita', default=False)
    auction = models.ForeignKey(Auction, verbose_name='Aukcja', on_delete=models.CASCADE)
    note = models.TextField(verbose_name='Notka', default="")
    user = models.ForeignKey(User, verbose_name='Użytkownik', on_delete=models.CASCADE)
    color = models.IntegerField(verbose_name='Kolor', default=0, choices=(
        (0, 'Biały'),
        (1, 'Zielony'),
        (2, 'Niebieski'),
        (3, 'Pomarańczowy'),
        (4, 'Czerwony'),
        (5, 'Złoty'),
    ))
    vin = models.CharField(verbose_name='VIN', default='',  max_length=32)
    invoice_price = models.IntegerField(verbose_name='Cena na fakturze [CHF]', null=True, blank=True)
    # add for optimization
    user_priv = models.ForeignKey(UserPrivate, verbose_name='Użytkownik', on_delete=models.CASCADE, null=True)
    auction_end_date = models.DateTimeField(verbose_name='Zakończenie', null=True)

    # def auction_link(self):
    #     try:
    #         bet_count = Bet.objects.filter(auction=self.auction).count()
    #         car_bets = '<a href="/admin/rest_api/bet/?q=%s" style="color:#ac0303;float:right;margin-right:5px">(%s)</a>' % (self.auction.ref_id, bet_count)
    #         provider_link = '<a href="%s" target="_blank" style="float:right">%s</a>' % (self.auction.get_provider_link(), self.auction.provider_name)
    #         link = '<a target="_blank" class="admin-auction-short-link" href="%s">Podgląd aukcji</a> ' % self.auction.get_link()
    #         if self.auction.get_provider_link() is not None:
    #             link += provider_link
    #         else:
    #             link += '<span style="float:right">%s</span>' % self.auction.provider_name
    #         link += car_bets
    #         return link
    #     except Exception as e:
    #         log_exception(e)
    #         return "Błąd linku"
    # auction_link.allow_tags = True
    # auction_link.short_description = 'Link do aukcji'

    def get_user(self):
        user = None
        try:
            user = UserPrivate.objects.get(user=self.user)
            return user
        except UserPrivate.DoesNotExist as e:
            log_exception(e)
        try:
            user = UserBusiness.objects.get(user=self.user)
        except UserBusiness.DoesNotExist:
            pass
        return user

    def __str__(self):
        return f"{self.user.username} - {self.auction.title} - {self.price} CHF"

    class Meta:
        verbose_name = 'Licytacja użytkownika'
        verbose_name_plural = 'Licytacje użytkownika'
        indexes = [
            models.Index(fields=['-auction_end_date', '-price', '-id']),
        ]

class TopBet(models.Model):
    auction = models.ForeignKey(Auction, verbose_name='Aukcja', on_delete=models.CASCADE)
    auction_end_date = models.DateTimeField(verbose_name='Zakończenie', blank=True, null=True)
    user = models.ForeignKey(UserPrivate, verbose_name='Użytkownik1', on_delete=models.CASCADE, blank=True, null=True)
    note = models.TextField(verbose_name='Notka', default="")
    bet = models.ForeignKey(Bet, on_delete=models.CASCADE, blank=True, null=True)
    bet_count = models.IntegerField(default=0)
    price = models.IntegerField(verbose_name='Cena [CHF]', default=0)
    color = models.IntegerField(verbose_name='Kolor', default=0, choices=(
        (0, 'Biały'),
        (1, 'Zielony'),
        (2, 'Niebieski'),
        (3, 'Pomarańczowy'),
        (4, 'Czerwony'),
        (5, 'Złoty'),
    ))
    scheduled = models.BooleanField(verbose_name='Automat', default=False)
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.auction.title} - {self.price} CHF"

    class Meta:
        verbose_name = 'Licytacja'
        verbose_name_plural = 'Licytacje'
        indexes = [
            models.Index(fields=['-auction_end_date', '-id']),
            models.Index(fields=['auction_end_date', '-id']),
            models.Index(fields=['color', '-auction_end_date', '-id']),
            models.Index(fields=['color', 'auction_end_date', '-id']),
        ]
    
class ScheduledBet(models.Model):
    price = models.IntegerField(verbose_name='Cena sugerowana [CHF]')
    price_max = models.IntegerField(verbose_name='Cena maksymalna [CHF]')
    betted = models.BooleanField(verbose_name='Wbita', default=False, editable=False)
    scheduled = models.BooleanField(verbose_name='Rozpoczęto', default=False, editable=False)
    bet = models.ForeignKey(Bet, verbose_name='Licytacja', on_delete=models.CASCADE, limit_choices_to={ 'auction_end_date__gte': timezone.now(),},)
    topbet = models.ForeignKey(TopBet, verbose_name='Licytacja', blank=True, null=True, on_delete=models.CASCADE, limit_choices_to={ 'auction_end_date__gte': timezone.now(),},)
    is_aggressive = models.BooleanField(verbose_name='Automat agresywny', default=False, editable=True)
    class Meta:
        verbose_name = 'Zaplanowana licytacja'
        verbose_name_plural = 'Zaplanowane licytacje'
        indexes = [
            models.Index(fields=['-bet']),
        ]


class BetSupervisor(Bet):
    def auction_link(self):
        link = '<a target="_blank" class="admin-auction-short-link" href="%s">%s</a> ' % (self.auction.get_link(), self.auction.title)
        return link
    auction_link.allow_tags = True
    auction_link.short_description = 'Aukcja'

    def user_bets(self):
        return ''
    user_bets.allow_tags = True
    user_bets.short_description = 'Licytacje użytkownika'

    def user_registered(self):
        user = None
        try:
            user = UserPrivate.objects.get(user=self.user)
            return str(user)
        except UserPrivate.DoesNotExist:
            pass

        try:
            user = UserBusiness.objects.get(user=self.user)
        except UserBusiness.DoesNotExist:
            pass

        return str(user)
    user_registered.short_description = 'Użytkownik'
    user_registered.allow_tags = True

    def auction_to_end(self):
        return self.auction.to_end_date()
    
    class Meta:
        proxy = True
        verbose_name = 'Licytacja'
        verbose_name_plural = 'Licytacje Podopiecznych'

class UserBusiness(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    user_top = models.ForeignKey(
        UserPrivate,
        on_delete=models.SET_NULL,
        verbose_name='Zarządca',
        blank=True,
        null=True,
    )

    # more data about user here
    accepted = models.BooleanField(default=False, verbose_name='Zaakceptowano')
    first_name = models.CharField(max_length=31,  blank=True, null=True, verbose_name='Imię')
    second_name = models.CharField(max_length=31, blank=True, null=True, verbose_name='Drugie imię')
    last_name = models.CharField(max_length=31, blank=True, null=True, verbose_name='Nazwisko')
    phone_number = models.CharField(max_length=31, blank=True, null=True, verbose_name='Telefon')
    slug = models.CharField(max_length=31, blank=True, null=True, verbose_name='slug')
    note = models.TextField(blank=True, null=True, verbose_name='Notka')
    lang = models.CharField(max_length=3, default='pl', verbose_name='Język', choices=(
            ('pl', 'Polski'),
            ('en', 'Angielski'),
            ('ru', 'Rosyjski'),
            ('de', 'Niemiecki'),
        )
    )

    business_name = models.CharField(max_length=63, blank=True, null=True, verbose_name='Nazwa firmy')
    nip_code = models.CharField(max_length=63, blank=True, null=True, verbose_name='NIP')
    country = models.CharField(max_length=63, blank=True, null=True, verbose_name='Kraj')
    postal_code = models.CharField(max_length=31, blank=True, null=True, verbose_name='Kod poczt.')
    city_name = models.CharField(max_length=31, blank=True, null=True, verbose_name='Miasto')
    street_name = models.CharField(max_length=127, blank=True, null=True, verbose_name='Ulica')
    home_number = models.CharField(max_length=63, blank=True, null=True, verbose_name='Dom/Mieszkanie')
    promocode = models.CharField(max_length=63, blank=True, null=True, verbose_name='Kod promo')
    #lookup = models.CharField(max_length=63)

    def bets(self):
        return '<a href="/admin/rest_api/bet/?q=%d">%s</a>' % (self.user.id, 'Licytacje')
    bets.allow_tags = True
    bets.short_description='Licytacje'

    def email(self):
        return self.user.email
    email.shortdescription = 'Email'

    def save(self, *args, **kwargs):
        self.lookup = self.__str__()
        super().save(*args, **kwargs)

    def __str__(self):
        return "{} {} ({})".format(
            self.first_name,
            self.last_name,
            self.user.email
        )

    class Meta:
        verbose_name = 'Uzytkownik biznesowy - firma'
        verbose_name_plural = 'Uzytkownicy biznesowi - firmy'

class AuctionUserFile(models.Model):
    uploaded = models.FileField(upload_to='user_files')
    comment = models.CharField(max_length=255,
                               blank=True,
                               null=True,
                               verbose_name='Komentarz',
                               help_text='Komentarz do pliku')
    auction = models.ForeignKey(
        Auction,
        #related_name='user_file',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        #related_name='user_file',
        on_delete=models.CASCADE,
    )
    class Meta:
        verbose_name = 'Plik dokumentu użytkownika'
        verbose_name_plural = 'Pliki dokumentów użytkowników'


class AuctionUserData(models.Model):
    first_name = models.CharField(max_length=127,
                               blank=True,
                               null=True,
                               verbose_name='Imie',
                               help_text='Imie')
    last_name = models.CharField(max_length=127,
                               blank=True,
                               null=True,
                               verbose_name='Nazwisko',
                               help_text='Nazwisko')
    address = models.CharField(max_length=127,
                               blank=True,
                               null=True,
                               verbose_name='Adres',
                               help_text='Adres')
    city = models.CharField(max_length=127,
                               blank=True,
                               null=True,
                               verbose_name='Miasto',
                               help_text='Miasto')
    country = models.CharField(max_length=127,
                               blank=True,
                               null=True,
                               verbose_name='Kraj',
                               help_text='Kraj')
    postcode = models.CharField(max_length=127,
                               blank=True,
                               null=True,
                               verbose_name='Kod pocztowy',
                               help_text='Kod pocztowy')
    nip = models.CharField(max_length=127,
                               blank=True,
                               null=True,
                               verbose_name='NIP',
                               help_text='NIP')
    accepted = models.BooleanField(default=False)
    auction = models.ForeignKey(
        Auction,
        #related_name='user_file',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        #related_name='user_file',
        on_delete=models.CASCADE,
    )


def save_auction(sender, instance, created, **kwargs):
    if not created:
        return
    number = instance.id
    A1 = chr(ord('A') + number // 10**5)
    number = number % 10**5
    A2 = chr(ord('A') + number // 10**4)
    number = number % 10**4
    A3 = chr(ord('A') + number // 10**3)
    number = number % 10**3
    Z1 = number // 10**2
    number = number % 10**2
    Z2 = number // 10
    number = number % 10
    Z3 = number
    UB = 'B'
    if instance.provider_name == 'axa':
        UB = 'W'
    elif instance.provider_name == 'rest':
        UB = 'R'
    elif instance.provider_name == 'allianz':
        UB = 'A'
    elif instance.provider_name == 'scc':
        UB = 'S'
    instance.ref_id = '%s%s%s-%s%s%s-%s' % (A1, A2, A3, Z1, Z2, Z3, UB)
    instance.save()


def save_bet(sender, instance, **kwargs):
    created = True if instance._state.adding else False

    if created:
        # starts websocket notification
        price = instance.price
        bets = Bet.objects.filter(auction=instance.auction).order_by('-price')
        skip = False
        if bets.count() > 0 and bets[0].price > price:
            skip = True

        if not skip and abs(instance.auction.end_date - datetime.now()).seconds < 60*60:
            import asyncio
            import websockets

            async def produce(message: str) -> None:
                async with websockets.connect('ws://%s:%s/' % (WEBSOCKET_HOST, WEBSOCKET_PORT)) as ws:
                    await ws.send(message)
                    await ws.recv()
            
            message = json.dumps({
                'user_fn': instance.get_user().first_name,
                'user_ln': instance.get_user().last_name,
                'auction': instance.auction.title,
                'end_date': instance.auction.to_end_date(),
            })
            
            try:
                loop = asyncio.get_event_loop()
            except:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                except:
                    pass
            
            try:
                loop.run_until_complete(produce(message=message))
            except Exception as e:
                log_exception(e)
            # ends websocket notification

    if created:
        notification, cr = BetNotificationsModel.objects.get_or_create(id=1)
        if not notification.activated or (notification.end_date and instance.auction.end_date > notification.end_date):
            return
        
        price = instance.price
        bets = Bet.objects.filter(auction=instance.auction).order_by('-price')
        if bets.count() > 0 and bets[0].price > price:
            return
        
        try:
            user = UserPrivate.objects.get(user=instance.user)
        except Exception as e:
            log_exception(e)
            return
            
        delta = timedelta(minutes=20)
        now = datetime.now()
        if now + delta > instance.auction.end_date:
            delta = instance.auction.end_date - now
            end_date = "za %d minut i %d sekund" % (delta.seconds//60,  delta.seconds%60)
        else:
            end_date = instance.auction.end_date.strftime("%d.%m o godzinie %H:%M:%S")
        
        user = UserPrivate.objects.get(user=instance.user)
        username = "%s %s" % (user.first_name, user.last_name)
        auction_name = instance.auction.title
        ref_id = instance.auction.ref_id

        body = "Pojawiła się nowa, najwyższa licytacja. Zakończenie %s. Cena: %s CHF. Użytkownik: %s. Aukcja: %s - %s." % (end_date, price, username, auction_name, ref_id)
        auth_token = ''
        account_sid = ''
        client = Client(account_sid, auth_token)
        from_num = '+48732140397'
        to_num = notification.phone_number
        
        message = client.messages.create(body=body, from_=from_num, to=to_num)
        instance.sms_sent = True

        return

    old_instance = Bet.objects.get(pk=instance.pk)

    if instance.color == 1 and old_instance.color != 1:
        user = UserPrivate.objects.get(user=instance.user)
        lang = user.lang
        with open(os.path.join(settings.BASE_DIR, 'web_app/translations.json'), 'r') as f:
            LANG_DICT = json.load(f)
        subject = LANG_DICT[lang]['email-13']
        message = '{} {},<br/><br/>'.format(LANG_DICT[lang]['email-7'], user.first_name)
        message += '<b>{} {}</b>, <b><span style="color:#017000;">{}</span>!</b>'.format(LANG_DICT[lang]['email-14'], instance.auction.title, LANG_DICT[lang]['email-15'])
        message += '<br/>{}: <a href="https://autazeszwajcarii.pl{}">https://autazeszwajcarii.pl{}</a><br/><br/>'.format(LANG_DICT[lang]['email-16'], instance.auction.get_link(), instance.auction.get_link())
        
        message += '<b>{}:</b><br/>'.format(LANG_DICT[lang]['email-21'])
        message += '<b>1. {}</b><br/>'.format(LANG_DICT[lang]['email-22'])
        message += '<b>2. {}</b><br/>'.format(LANG_DICT[lang]['email-23'])
        message += '<b>3. {}</b><br/>'.format(LANG_DICT[lang]['email-24'])
        message += '<i>* {}</i><br/><br/>'.format(LANG_DICT[lang]['email-25'])
        message += '{}<br/>'.format(LANG_DICT[lang]['email-27'])
        message += '<b>{}</b>.'.format(LANG_DICT[lang]['email-26'])
        message += '<br/><br/>%s,<br/>%s' %(LANG_DICT[lang]['email-19'], LANG_DICT[lang]['email-20'])

        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_NORESPONSE,
                [user.user.email],
                html_message=message,
            )
        except Exception as e:
            log_exception(e)


def post_save_bet(sender, instance, created, **kwargs):
    if not created:
        return
    
    if instance.auction.provider_name == 'axa':
        vin = '' #?
    elif instance.auction.provider_name == 'rest':
        if 'Chassis-Nr.' in instance.auction.data:
            vin = instance.auction.data['Chassis-Nr.']
        else:
            vin = ''
    elif instance.auction.provider_name == 'allianz':
        if 'FINNr' in instance.auction.data:
            vin = instance.auction.data['FINNr']
        else:
            vin = ''
    elif instance.auction.provider_name == 'scc':
        if 'VIN' in instance.auction.data:
            vin = instance.auction.data['VIN']
        else:
            vin = ''
    
    instance.vin = vin
    instance.save()


def save_short_url(sender, instance, **kwargs):
    created = True if instance._state.adding else False
    if created:
        existed = 1
        while existed:
            short_url = 'https://autazeszwajcarii.pl/_' + ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(6))
            existed_list = ShortUrlModel.objects.filter(short_url=short_url)
            existed = len(existed_list)
        instance.short_url = short_url


def user_unicode(self):
    try:
        user = UserPrivate.objects.get(user=self)
        user = "%s %s" % (user.first_name, user.last_name)
    except Exception as e:
        user = 'Uzytkownik systemowy'
    return user
User.__unicode__ = user_unicode
User.__str__ = user_unicode


def delete_user(sender, instance, **kwargs):
    email = instance.email()
    user = User.objects.get(email=email)
    user.delete()


def delete_auction(sender, instance, **kwargs):
    if not instance.min_image:
        return

    storage_path = '/web_apps/swiss_website/auction_photos/'
    if storage_path in instance.min_image.path and instance.min_image.path != storage_path:
        base_path = os.path.dirname(instance.min_image.path)
        file_name = os.path.basename(instance.min_image.path)

        try:
            extension = file_name.split('.')[-1]
            left = file_name.split('_')[0]
            file_to_del = '%s.%s' % (left, extension)
            file_to_del = file_to_del.replace('_', ' ')
            os.remove(os.path.join(base_path, file_to_del))
        except Exception as e:
            logger.warning('Unable to find min_image image %s' % file_to_del)
        instance.min_image.delete(False)

def delete_photo(sender, instance, **kwargs):
    if not instance.image:
        return

    storage_path = '/web_apps/swiss_website/auction_photos/'
    if storage_path in instance.image.path and instance.image.path != storage_path:
        try:
            a = instance.image.path
            b = a.split('.')[:-1]
            b = '.'.join(b)
            c = a.split('.')[-1]
            no_logo_path = b + '_no_logo.' + c
            os.remove(no_logo_path)
        except Exception as e:
            logger.warning('Unable to find _no_logo image %s' % no_logo_path)
        instance.image.delete(False)


pre_delete.connect(delete_auction, sender=Auction)
pre_delete.connect(delete_photo, sender=AuctionPhoto)
post_save.connect(save_auction, sender=Auction)
pre_save.connect(save_short_url, sender=ShortUrlModel)
pre_save.connect(save_bet, sender=Bet)
post_save.connect(post_save_bet, sender=Bet)
post_delete.connect(delete_user, sender=UserPrivate)
