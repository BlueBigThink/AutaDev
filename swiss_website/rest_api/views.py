import os
import json
import subprocess
from datetime import datetime
from configparser import ConfigParser

from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.http import Http404
from django.http.request import QueryDict
from django.views.generic import TemplateView

from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework import permissions

from web_app.language_manager import LanguageManager
from web_app.utils import log_exception

from .models import (
    Auction,
    WatchAuction,
    Bet,
    WatchTag,
    ShortUrlModel,
    BetNotificationsModel,
    UserPrivate,
    TopBet
)
from .serializers import (
    AuctionSerializer,
    AuctionMinSerializer,
    AuctionMinExternalSerializer,
    AuctionExternalSerializer
)

from twilio.rest import Client


class BetNotificationsAdminView(TemplateView):
    template_name = 'admin/bet_notifications.html'

    def get(self, request):
        notification, cr = BetNotificationsModel.objects.get_or_create(id=1)
        end_date = notification.end_date.strftime("%d.%m.%Y") if notification.end_date else ""
        end_time = notification.end_date.strftime("%H:%M:%S") if notification.end_date else ""

        auth_token = ''
        account_sid = ''
        client = Client(account_sid, auth_token)
        balance = client.api.v2010.balance.fetch()
        balance_str = "%.2f %s" % (float(balance.balance), balance.currency)

        data = {
            'phone_number': notification.phone_number,
            'activated': notification.activated,
            'end_date': end_date,
            'end_time': end_time,
            'balance': balance_str,
            'balance_warning': float(balance.balance) < 5
        }
        return render(request, self.template_name, data)

    def post(self, request):
        notification, cr = BetNotificationsModel.objects.get_or_create(id=1)
        phone_number = request.POST.get('phone_number').strip()
        activated = (request.POST.get('activated') or False) and True
        end_date = request.POST.get('end_date_0').strip()
        end_time = request.POST.get('end_date_1').strip()

        auth_token = ''
        account_sid = ''
        client = Client(account_sid, auth_token)
        balance = client.api.v2010.balance.fetch()
        balance_str = "%.2f %s" % (float(balance.balance), balance.currency)

        if (end_date and not end_time) or (not end_date and end_time):
            end_date = notification.end_date.strftime("%d.%m.%Y") if notification.end_date else ""
            end_time = notification.end_date.strftime("%H:%M:%S") if notification.end_date else ""

            data = {
                'phone_number': notification.phone_number,
                'activated': notification.activated,
                'alert': True,
                'success': False,
                'end_date': end_date,
                'end_time': end_time,
                'balance': balance_str,
                'balance_warning': float(balance.balance) < 5
            }
            return render(request, self.template_name, data)

        if not phone_number.startswith("+48"):
            end_date = notification.end_date.strftime("%d.%m.%Y") if notification.end_date else ""
            end_time = notification.end_date.strftime("%H:%M:%S") if notification.end_date else ""

            data = {
                'phone_number': notification.phone_number,
                'activated': notification.activated,
                'alert': True,
                'success': False,
                'end_date': end_date,
                'end_time': end_time,
                'balance': balance_str,
                'balance_warning': float(balance.balance) < 5
            }
            return render(request, self.template_name, data)

        try:
            notification.phone_number = phone_number
            notification.activated = activated
            if end_date:
                notification.end_date = datetime.strptime(
                    "%s %s" % (end_date, end_time), 
                    "%d.%m.%Y %H:%M:%S")
            else:
                notification.end_date = None
            notification.save()

            data = {
                'phone_number': notification.phone_number,
                'activated': notification.activated,
                'alert': True,
                'success': True,
                'end_date': end_date,
                'end_time': end_time,
                'balance': balance_str,
                'balance_warning': float(balance.balance) < 5
            }
            return render(request, self.template_name, data)
        except:
            end_date = notification.end_date.strftime("%d.%m.%Y") if notification.end_date else ""
            end_time = notification.end_date.strftime("%H:%M:%S") if notification.end_date else ""

            data = {
                'phone_number': notification.phone_number,
                'activated': notification.activated,
                'alert': True,
                'success': False,
                'end_date': end_date,
                'end_time': end_time,
                'balance': balance_str,
                'balance_warning': float(balance.balance) < 5
            }
            return render(request, self.template_name, data)


class AutomateDashboardAdminView(TemplateView):
    template_name = 'admin/automate_dashboard.html'
    template_name_rest = 'admin/automate_dashboard_rest.html'
    template_name_scc = 'admin/automate_dashboard_scc.html'
    template_name_scc_codes = 'admin/automate_dashboard_scc_codes.html'

    def get(self, request, provider=None):
        if not provider:
            data = dict()
            with open('/web_apps/app_download/allianz.status') as f:
                data["allianz"] = json.load(f)
            with open('/web_apps/app_download/axa.status') as f:
                data["axa"] = json.load(f)
            with open('/web_apps/app_download/scc.status') as f:
                data["scc"] = json.load(f)
            with open('/web_apps/app_download/rest.status') as f:
                data["rest"] = json.load(f)

            return render(request, self.template_name, data)
        elif provider == 'rest':
            return render(request, self.template_name_rest)
        elif provider == 'scc':
            return render(request, self.template_name_scc)
        elif provider == 'scc_codes':
            config = ConfigParser()
            config.read('/web_apps/app_download/codes/scc.codes')
            data = {
                "codes": config.items("codes")
            }
            return render(request, self.template_name_scc_codes, data)
        else:
            raise Http404

    def post(self, request, provider):
        if provider == 'rest':
            try:
                config = ConfigParser()
                config.read('/web_apps/app_download/codes/rest.codes')
                config['account']['login'] = request.POST.get('username')
                config['account']['pass'] = request.POST.get('password')
                with open('/web_apps/app_download/codes/rest.codes', 'w') as f:
                    config.write(f)
                    
                data = {
                    "status_success": "Dane logowania zmieniono pomyślnie!"
                }
            except Exception as e:
                log_exception(e)
                data = {
                    "status_error": "Podczas przetwarzania żądania wystąpił błąd. Skontaktuj się z Administratorem, aby uniknąć problemów z automatami."
                }
            return render(request, self.template_name_rest, data)
        elif provider == 'scc':
            try:
                config = ConfigParser()
                config.read('/web_apps/app_download/codes/scc.codes')
                config['account']['login'] = request.POST.get('username')
                config['account']['pass'] = request.POST.get('password')
                with open('/web_apps/app_download/codes/scc.codes', 'w') as f:
                    config.write(f)
                    
                data = {
                    "status_success": "Dane logowania zmieniono pomyślnie!"
                }
            except Exception as e:
                log_exception(e)
                data = {
                    "status_error": "Podczas przetwarzania żądania wystąpił błąd. Skontaktuj się z Administratorem, aby uniknąć problemów z automatami."
                }
            return render(request, self.template_name_scc, data)
        elif provider == 'scc_codes':
            try:
                config = ConfigParser()
                config.read('/web_apps/app_download/codes/scc.codes')

                for code in request.POST:
                    try:
                        if int(code) > 0: 
                            config['codes'][code] = request.POST.get(code)
                    except:
                        pass

                with open('/web_apps/app_download/codes/scc.codes', 'w') as f:
                    config.write(f)
                    
                data = {
                    "status_success": "Kody do logowania zmieniono pomyślnie!"
                }
            except Exception as e:
                log_exception(e)
                data = {
                    "status_error": "Podczas przetwarzania żądania wystąpił błąd. Skontaktuj się z Administratorem, aby uniknąć problemów z automatami."
                }
            return render(request, self.template_name_scc_codes, data)

        else:
            raise Http404


        file_content = request.POST.get('file_content', '')

        if file_content:
            with open(self.translations_path, 'w') as f:
                f.write(file_content)
            subprocess.call("supervisorctl reload", shell=True)
            info = {
                'success': 'Plik zaktualizowano pomyślnie!'
            }
        else:
            with open(self.translations_path, 'r') as f:
                file_content = f.read()
            info = {
                'error': 'Coś poszło nie tak, dzwoń prędko do Szefa Administracji Strony!'
            }

        data = {
            'file_content': file_content,
            'info': info,
        }
        return render(request, self.template_name, data)


class LanguageAdminView(TemplateView):
    template_name = 'admin/languages.html'
    translations_path = '/web_apps/swiss_website/web_app/translations.json'

    def get(self, request):
        file_content = ''

        with open(self.translations_path, 'r', encoding="utf-8") as f:
            file_content = f.read()

        data = {
            'file_content': file_content,
            'info': {},
        }
        return render(request, self.template_name, data)

    def post(self, request):
        file_content = request.POST.get('file_content', '')

        if file_content:
            try:
                json.loads(file_content)

                lm = LanguageManager()
                lm.update_trans(file_content)

                info = {
                    'success': 'Tłumaczenia zaktualizowano pomyślnie!'
                }
            except ValueError as err:
                log_exception(err)
                info = {
                    'error': 'Format pliku jest niepoprawny, proszę wprowadź teksty w poprawnym formacie.'
                }
        else:
            with open(self.translations_path, 'r') as f:
                file_content = f.read()
            info = {
                'error': 'Coś poszło nie tak, dzwoń prędko do Szefa Administracji Strony!'
            }

        data = {
            'file_content': file_content,
            'info': info,
        }
        return render(request, self.template_name, data)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Instance must have an attribute named `owner`.
        return request.user.is_staff


class ExternalAuctionList(GenericAPIView):
    """
    List all auctions without details
    """
    permission_classes = ()
    serializer_class = AuctionMinExternalSerializer
    queryset = ''

    def is_authenticated(self, request):
        if request.META.get('HTTP_AUTHORIZATION', '').strip() == '7b15234517ab44ea448a67f283bc9591528fe64f':
            return True
        return False

    def get(self, request, format=None):
        if not self.is_authenticated(request):
            return Response(status=401)
        
        now = datetime.now()
        auctions = Auction.objects.filter(
           end_date__gte=now,
           provider_name='scc'
        )
        serializer = AuctionMinExternalSerializer(auctions, many=True)
        paginator = Paginator(serializer.data, settings.PAGE_SIZE)
        auctions_ret = paginator.page(1)

        return Response(list(auctions_ret))


class ExternalAuctionDetails(APIView):
    """
    Retrieve, update or delete an auction instance.
    """
    permission_classes = ()

    def is_authenticated(self, request):
        if request.META.get('HTTP_AUTHORIZATION', '').strip() == '7b15234517ab44ea448a67f283bc9591528fe64f':
            return True
        return False

    def get_object(self, pk):
        try:
            now = datetime.now()
            return Auction.objects.get(pk=pk, end_date__gte=now, provider_name='scc')
        except Auction.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        if not self.is_authenticated(request):
            return Response(status=401)

        auction = self.get_object(pk)
        serializer = AuctionExternalSerializer(auction)
        data = serializer.data
        
        for i in range(len(data['photos'])):
            photo_path = data['photos'][i]
            photo_new_path = os.path.join('/auction_photos/no_logo/', os.path.basename(photo_path))
            data['photos'][i] = photo_new_path

        return Response(data)


class StopObserveView(GenericAPIView):
    """
    Adding auction to observe
    """

    def post(self, request, format=None):
        if not request.user.is_authenticated:
            raise Http404

        auction_id = int(request.POST['auction_id'])
        try:
            WatchAuction.objects.get(
                user=request.user,
                auction__id=auction_id
            ).delete()
        except WatchAuction.DoesNotExist:
            raise Http404

        return Response(status=status.HTTP_201_CREATED)


class SearchAddView(GenericAPIView):
    def post(self, request, format=None):
        if not request.user.is_authenticated:
            raise Http404

        keyword = request.POST['keyword']
        tag, cr = WatchTag.objects.get_or_create(tag=keyword, user=request.user)

        return Response(status=status.HTTP_201_CREATED)


class SearchRemoveView(GenericAPIView):
    def post(self, request, format=None):
        if not request.user.is_authenticated:
            raise Http404

        keyword = request.POST['keyword']
        try:
            tag = WatchTag.objects.get(tag=keyword, user=request.user)
            tag.delete()
        except WatchTag.DoesNotExist:
            pass

        return Response(status=status.HTTP_201_CREATED)


class BetView(GenericAPIView):
    def post(self, request, format=None):
        if not request.user.is_authenticated:
            raise Http404
        try:
            userpriv = UserPrivate.objects.get(user=request.user) 
            if not userpriv.accepted:
                raise Http404
        except UserPrivate.DoesNotExist:
            raise Http404

        offer = int(request.POST['offer'])
        auction_id = int(request.POST['auction_id'])

        try:
            auction = Auction.objects.get(id=auction_id)
        except Auction.DoesNotExist:
            raise Http404

        existed_count = Bet.objects.filter(auction=auction, user=request.user, price=offer).count()

        if existed_count > 0:
            return Response(status=status.HTTP_201_CREATED)

        bet = Bet(
            user=request.user,
            auction=auction,
            price=offer,
            user_prev=userpriv,
            auction_end_date=auction.end_date
        )
        bet.save()

        topbet, created = TopBet.objects.get_or_create(auction=auction)
        topbet.bet_count += 1
        if created:
            # set auction info to active bet
            topbet.auction_end_date = bet.auction.end_date
        if created or topbet.price < offer:
            # set user and price to active bet
            topbet.user = userpriv
            topbet.bet = bet
            topbet.price = offer
            topbet.color = bet.color
        try:
            auction = Auction.objects.get(id=auction_id)
        except Auction.DoesNotExist:
            raise Http404

        watch, cr = WatchAuction.objects.get_or_create(
            auction=auction,
            user=request.user
        )

        return Response(status=status.HTTP_201_CREATED)


class PublishView(GenericAPIView):
    def post(self, request, format=None):
        if not request.user.is_superuser:
            raise Http404

        auction_id = int(request.POST['auction_id'])
        try:
            auction = Auction.objects.get(id=auction_id)
        except Auction.DoesNotExist:
            raise Http404
        
        auction.published = True
        auction.save()

        return Response(status=status.HTTP_200_CREATE)


class AddToObserved(GenericAPIView):
    """
    Adding auction to observe
    """

    def post(self, request, format=None):
        if not request.user.is_authenticated:
            raise Http404

        auction_id = int(request.POST['auction_id'])
        try:
            auction = Auction.objects.get(id=auction_id)
        except Auction.DoesNotExist:
            raise Http404

        watch, cr = WatchAuction.objects.get_or_create(
            auction=auction,
            user=request.user
        )

        return Response(status=status.HTTP_201_CREATED)


class AuctionList(GenericAPIView):
    """
    List all auctions without details
    """
    permission_classes = (IsAdminOrReadOnly, )
    serializer_class = AuctionMinSerializer
    queryset = ''

    def get(self, request, format=None):
        now = datetime.now()
        auctions = Auction.objects.filter(
           end_date__gte=now
        )
        serializer = AuctionMinSerializer(auctions, many=True)
        paginator = Paginator(serializer.data, settings.PAGE_SIZE)
        page = request.GET.get('page')

        try:
            auctions_ret = paginator.page(page)
        except PageNotAnInteger:
            auctions_ret = paginator.page(1)
        except EmptyPage:
            raise Http404

        for i in range(0, len(auctions_ret)):
            check = False

            if request.user.is_authenticated:
                try:
                    WatchAuction.objects.get(
                        auction__id=auctions_ret[i]['id'],
                        user=request.user
                    )
                    auctions_ret[i]['observed'] = True
                    check = True
                except WatchAuction.DoesNotExist:
                    pass

            if not check:
                auctions_ret[i]['observed'] = False

        return Response(list(auctions_ret))

    def post(self, request, format=None):
        data = request.data
        if isinstance(request.data, QueryDict):
            data = request.data.dict()

        data['photos'] = list()

        for photo in request.FILES.values():
            data['photos'].append(photo)

        data['data'] = json.loads(data['data'], object_pairs_hook=lambda x: dict(x))
        try:
            auction = Auction.objects.get(provider_id=data['provider_id'], provider_name=data['provider_name'])
            serializer = AuctionSerializer(auction, data=data)
        except Auction.DoesNotExist:
            serializer = AuctionSerializer(data=data)
        except Exception as e:
            return Response(str(e), status=status.status.HTTP_400_BAD_REQUEST)
        try:
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except:
            pass
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AuctionDetails(APIView):
    """
    Retrieve, update or delete an auction instance.
    """
    def get_object(self, pk):
        try:
            return Auction.objects.get(pk=pk)
        except Auction.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        auction = self.get_object(pk)
        serializer = AuctionSerializer(auction)

        return Response(serializer.data)

    def put(self, request, pk, format=None):
        auction = self.get_object(pk)
        serializer = AuctionSerializer(auction, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        auction = self.get_object(pk)
        auction.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
