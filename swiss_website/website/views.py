import os
import logging
import binascii
import hashlib
from time import time
import re
import requests
from datetime import datetime, timedelta

from django.utils.encoding import uri_to_iri, iri_to_uri
from django.conf import settings
from django import template
from django.core.mail import send_mail, BadHeaderError
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, Http404
from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, FormView, View
from django.views.generic.base import RedirectView
from django.db.models import Q, Max
from django.views.decorators.csrf import requires_csrf_token
from django.core.cache import cache

from rest_api.models import Auction, UserPrivate, UserBusiness, Bet, WatchAuction, WatchTag, TopAuction, AuctionUserData, AuctionUserFile, ShortUrlModel, Banner, MarketingCampaign
from rest_api.serializers import AuctionMinSerializer

from .forms import LoginForm, RegisterForm, ChangePasswordForm
from web_app.language_manager import LanguageManager
from web_app.settings import MARKETING_SOURCE_COOKIE_NAME
from web_app.utils import log_exception

from django.views.decorators.cache import cache_page
logger = logging.getLogger(__name__)

languageManager = LanguageManager()


def custom_render(request, template_name, context=None, content_type=None, status=None, using=None):
    lm = LanguageManager()

    if not context:
        context = dict()
    if 'lang' not in context:
        context['lang'] = lm.get_lang(request.user, request)
    if 'translations' not in context:
        context['translations'] = lm.get_trans_dict()

    return render(request, template_name, context, content_type, status, using)


class FaqView(TemplateView):
    template_name = 'faq.html'

    def get(self, request):
        path = request.get_full_path()
        if 'ua' in path:
            lang = 'ua'
        else:
            lang = languageManager.get_lang(request.user, request)
        return custom_render(request, self.template_name, {'lang': lang})


class ShortUrlRedirectView(RedirectView):
    permanent = True
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        short_url = 'https://autazeszwajcarii.pl/_' + kwargs['short_url']
        try:
            url_object = ShortUrlModel.objects.get(short_url=short_url)
            url = url_object.url
            return url
        except:
            pass

        try:
            url_object = ShortUrlModel.objects.get(short_url=short_url[:-1])
            url = url_object.url
            return url
        except:
            url = 'https://autazeszwajcarii.pl/aukcje'

        return url


@method_decorator(login_required, name='dispatch')
class DownloadCenterView(TemplateView):
    template_name = 'download_center.html'
    entries_per_page = 30
    def get(self, request, page_id=1):
        max_bet = None
        page_id = int(page_id)
        if page_id < 1:
            page_id = 1

        if not request.user.is_superuser and not request.user.groups.filter(name='InvoiceAdmin').exists():
            raise Http404

        bets = Bet.objects.order_by('auction__pk', '-price').distinct('auction__pk')
        bets_max = Bet.objects.filter(pk__in=bets).filter(color__in=[1,5]).values('auction__pk')
        auctions = Auction.objects.filter(pk__in=bets_max).order_by('-end_date')[(page_id-1)*30:page_id*30]

        search = request.GET.get('ref', None)
        if search:
            auctions = Auction.objects.filter(title__icontains=search, pk__in=bets_max).order_by('-end_date') |  Auction.objects.filter(ref_id=search, pk__in=bets_max)
        table_data = list()

    
        for auction in auctions:
            try:
                user_data = AuctionUserData.objects.get(auction=auction)
                max_bet = Bet.objects.filter(accepted=True, auction=auction).latest('price')
            except AuctionUserData.DoesNotExist:
                user_data = None
                try:
                    max_bet = Bet.objects.filter(accepted=True, auction=auction).latest('price')
                    user = max_bet.user
                except Bet.DoesNotExist:
                    user = None
                    continue

            ref_id = auction.provider_id
            provider_name = auction.provider_name
            vin = max_bet.vin
            if vin:
                ref_id = vin
 
            user_files = AuctionUserFile.objects.filter(auction=auction)
            entry = {
                'provider_name': provider_name,
                'ref_id': ref_id,
                'title': auction.title,
                'end_date': auction.end_date,
                'link': auction.get_link,
                'data': user_data,
                'files': user_files,
                'auction_id': auction.id,
                'user': user_data.user if user_data else user ,
                'max_bet_id': max_bet.id if max_bet is not None else '',
                'invoice': 'false',
                'invoice_price': max_bet.invoice_price,
                'vin': vin,
            }
            if user_data:
                entry['invoice'] = 'true' if user_data.nip else 'false', # if max_bet is not None and max_bet.color == 5 else 'false',

            table_data.append(entry)

        data = {
            'table': table_data,
            'page_id': page_id,
        }
        return custom_render(request, self.template_name, data)


@method_decorator(login_required, name='dispatch')
@method_decorator(requires_csrf_token, name='dispatch')
class UploadCenterView(TemplateView):
    template_name = 'upload_center.html'

    def get(self, request, auction_id, file_id=None):
        if not self.is_user_have_access(auction_id, request.user) and not request.user.groups.filter(name='InvoiceAdmin').exists() and not request.user.is_superuser:
            raise Http404
        if file_id != None:
            file_download = get_object_or_404(AuctionUserFile, id=file_id)
            file_path = os.path.join('/web_apps/swiss_website/', uri_to_iri(file_download.uploaded.url[16:]))
            if os.path.exists(file_path):
                with open(file_path, 'rb') as fh:
                    response = HttpResponse(fh.read())
                    response['Content-Disposition'] = 'attachment; filename=' + iri_to_uri(os.path.basename(file_path))
                    response['Content-Type'] = 'application/octet-stream'
                    return response

            raise Http404
        if request.user.email == 'noreply.autazeszwajcarii@gmail.com' or request.user.is_superuser or request.user.groups.filter(name='InvoiceAdmin').exists():
            raise Http404
        auction = get_object_or_404(Auction, ref_id=auction_id)
        auction_user_data, cr = AuctionUserData.objects.get_or_create(
            auction = auction,
            user = request.user,
        )
        files = AuctionUserFile.objects.filter(auction=auction, user=request.user)

        data = {
            'auction_id': auction_id,
            'first_name': auction_user_data.first_name,
            'last_name': auction_user_data.last_name,
            'address': auction_user_data.address,
            'city': auction_user_data.city,
            'country': auction_user_data.country,
            'postcode': auction_user_data.postcode,
            'nip': auction_user_data.nip,
            'files': files,
            'accepted': auction_user_data.accepted,
            'lang': languageManager.get_lang(request.user, request),
        }
        return custom_render(request, self.template_name, data)

    def post(self, request, auction_id):
        if not self.is_user_have_access(auction_id, request.user):
            raise Http404
        auction = get_object_or_404(Auction, ref_id=auction_id)
        user_data = request.POST.dict()
        if user_data.get('first_name', None) != None:
            auction_user_data, cr = AuctionUserData.objects.get_or_create(
                auction = auction,
                user = request.user,
            )
            auction_user_data.first_name = user_data.get('first_name', '')
            auction_user_data.last_name = user_data.get('last_name', None)
            auction_user_data.address = user_data.get('address', None)
            auction_user_data.city = user_data.get('city', None)
            auction_user_data.country = user_data.get('country', None)
            auction_user_data.postcode = user_data.get('postcode', None)
            auction_user_data.nip = user_data.get('nip', None)
            auction_user_data.accepted = True if user_data.get('accepted', None) else False
            auction_user_data.save()
        else:
            try:
                comment = request.POST.get('comment')
                uploaded = request.FILES.get('user_file')
                if not uploaded:
                    return redirect('/konto/pliki/%s/' % auction_id)
                
                if not uploaded.name.endswith('.png') and not uploaded.name.endswith('.jpg') and not uploaded.name.endswith('.pdf') and not uploaded.name.endswith('.jpeg') and not uploaded.name.endswith('.PNG') and not uploaded.name.endswith('.JPG') and not uploaded.name.endswith('.PDF') and not uploaded.name.endswith('.JPEG'):
                    return redirect('/konto/pliki/%s/' % auction_id)
                data_file = AuctionUserFile(
                    auction=auction,
                    user=request.user,
                    uploaded=uploaded,
                    comment=comment,
                )
                data_file.save()
            except Exception as e:
                log_exception(e)
                return redirect('/konto/pliki/%s/' % auction_id)
            

        return redirect('/konto/pliki/%s/' % auction_id)

    def is_user_have_access(self, auction, user):
        bet_exists = Bet.objects.filter(accepted=True, auction__ref_id=auction, color__in=[1, 5], user=user).exists()
        if bet_exists:
            return True
        return False


class EntryView(TemplateView):
    template_name = 'enter.html'

    def get(self, request):
        path = request.get_full_path()
        if 'ua' in path:
            lang = 'ua'
        else:
            lang = languageManager.get_lang(request.user, request)
        return custom_render(request, self.template_name, {'lang': lang})


class HomeView(TemplateView):
    template_name = 'home.html'

    def get(self, request):
        return custom_render(request, self.template_name, {'lang': languageManager.get_lang(request.user, request)})


class CompanyView(TemplateView):
    template_name = 'company.html'

    def get(self, request):
        return custom_render(request, self.template_name, {'lang': languageManager.get_lang(request.user, request)})


class RulesView(TemplateView):
    template_name = 'rules.html'

    def get(self, request):
        return custom_render(request, self.template_name, {'lang': languageManager.get_lang(request.user, request)})


class CurrenciesView(View):
    def get(self, request):
        try:
            url = 'https://kantor.com.pl/'
            response = requests.get(url)

            chf = re.search('CHF</td><td><b>(?P<chf_buy>[0-9\.]+)</b></td><td><b>(?P<chf_sell>[0-9\.]+)</b>', response.text)
            eur = re.search('EUR</td><td><b>(?P<eur_buy>[0-9\.]+)</b></td><td><b>(?P<eur_sell>[0-9\.]+)</b>', response.text)

            chf_price = chf.group('chf_buy') if chf.group('chf_buy') > chf.group('chf_sell') else chf.group('chf_sell')
            eur_price = eur.group('eur_buy') if eur.group('eur_buy') > eur.group('eur_sell') else eur.group('eur_sell')
            cache.set('chf_price', chf_price, None)
            cache.set('eur_price', eur_price, None)
        except requests.exceptions.ConnectionError as e:
            chf_price = cache.get('chf_price')
            eur_price = cache.get('eur_price')
        except AttributeError as e:
            chf_price = cache.get('chf_price')
            eur_price = cache.get('eur_price')

        return JsonResponse({'chf': chf_price, 'eur': eur_price})


class AdsView(TemplateView):
    template_name = 'ads.html'

    def get(self, request):
        return custom_render(request, self.template_name, {'lang': languageManager.get_lang(request.user, request)})


@method_decorator(login_required, name='dispatch')
class CalculatorView(View):
    template_name = 'calculator.html'

    def get(self, request, format=None):
        if request.user.is_superuser:
            is_admin = User.objects.filter(pk=request.user.pk, groups__name='CalculatorAdmin').exists()
            return custom_render(request, self.template_name, {'is_admin': is_admin, 'lang': request.COOKIES.get('lang', 'pl')})

        try:
            user_priv = UserPrivate.objects.get(user=request.user)
            calc_enabled = user_priv.calculator_enabled
        except:
            calc_enabled = False
        
        is_admin = User.objects.filter(pk=request.user.pk, groups__name='CalculatorAdmin').exists()
        
        if not calc_enabled:
            return redirect('/')
        return custom_render(request, self.template_name, {'is_admin': is_admin, 'lang': languageManager.get_lang(request.user, request)})


class ContactView(View):
    template_name = 'contact.html'

    def get(self, request):
        return custom_render(request, self.template_name, {'lang': languageManager.get_lang(request.user, request), 'recaptcha_site_key':settings.GOOGLE_RECAPTCHA_SITE_KEY})

    def post(self, request):
        subject = request.POST.get('subject', '')
        message = request.POST.get('content', '')
        name = request.POST.get('name', '')
        from_email = request.POST.get('email', '')

        if subject and message and from_email:
            try:
                #''' reCAPTCHA validation '''
                recaptcha_response = request.POST.get('g-recaptcha-response')
                data = {
                    'secret': settings.GOOGLE_RECAPTCHA_SECRET_KEY,
                    'response': recaptcha_response
                }
                r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
                result = r.json()

                #''' if reCAPTCHA returns True '''
                if result['success']:
                    send_mail("{} [{}] - {}".format(subject, name, from_email), message, settings.EMAIL_FROM_BOT, [settings.EMAIL_TARGET])
                else:
                    logger.warning("reCAPTCHA failed")
            except BadHeaderError:
                return JsonResponse({'success': False})
            except Exception as e:
                log_exception(e)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'sucess': True})


class AuctionListView(TemplateView):
    template_name = 'auctions.html'

    def get(self, request, page=1):
        auctions = self.filter_auctions(request).order_by('-highlighted', 'end_date')
        auctions_ret = auctions

        for i in range(0, len(auctions_ret)):
            auctions_ret[i].link = '/aukcje/licytacja/{}/{}'.format(
                auctions_ret[i].id,
                re.sub('[^0-9a-zA-Z]+', '-', auctions_ret[i].title.lower())
            )
            end_date = auctions_ret[i].end_date.strftime("%d-%m-%Y %H:%M:%S")
            auctions_ret[i].finish_date = end_date

            if request.user.is_authenticated:
                try:
                    auctions_ret[i].observed = WatchAuction.objects.get(
                        user=request.user,
                        auction__id=auctions_ret[i].id
                    )
                except WatchAuction.DoesNotExist:
                    pass
                except:
                    pass

        paging_to_left = max(1, page-3)
        paging_to_right = 1
        current_year = datetime.now().year

        latest_top_auctions = TopAuction.objects.filter(auction__end_date__gte=datetime.now()).order_by('auction__end_date')
        latest_top_info = TopAuction.objects.filter(auction=None).order_by('-id')
        merged = list(latest_top_info) + list(latest_top_auctions)

        latest_top_auctions = merged

        lang = languageManager.get_lang(request.user, request)
        main14 = languageManager.get_trans_by_lang(lang, 'main-14')
        main12 = languageManager.get_trans_by_lang(lang, 'main-12')
        main13 = languageManager.get_trans_by_lang(lang, 'main-13')
        main16 = languageManager.get_trans_by_lang(lang, 'main-16')
        main14 = languageManager.get_trans_by_lang(lang, 'main-14')
        main15 = languageManager.get_trans_by_lang(lang, 'main-15')
        main18 = languageManager.get_trans_by_lang(lang, 'main-18')
        main17 = languageManager.get_trans_by_lang(lang, 'main-17')
        main19 = languageManager.get_trans_by_lang(lang, 'main-19')
        main20 = languageManager.get_trans_by_lang(lang, 'main-20')
        try:
            banner = Banner.objects.filter(published=True).first()
        except IndexError:
            banner = None

        translations = languageManager.get_trans_dict()
        return custom_render(
            request,
            self.template_name,
            {
                'lang': lang,
                'auctions': auctions_ret,
                'page': page,
                'max_page': 1,
                'paging_to_left': paging_to_left,
                'paging_to_right': paging_to_right,
                'data_form': request.GET,
                'current_year': current_year,
                'latest_top_auctions': latest_top_auctions,
                'main12': main12,
                'main13': main13,
                'main14': main14,
                'main15': main15,
                'main16': main16,
                'main17': main17,
                'main18': main18,
                'main19': main19,
                'main20': main20,
                'banner': banner,
                'translations': translations,
             }
        )

    def filter_auctions(self, request):
        now = datetime.now()

        if request.GET.get('brand') is None:
            return Auction.objects.filter(
                end_date__gte=now,
		published=True,
            )

        auctions = Auction.objects.filter(
           end_date__gte=now,
           published=True,
        )

        if request.GET.get('brand'):
            auctions = auctions.filter(
                brand__name__iexact=request.GET.get('brand')
            )

        if request.GET.get('run_from'):
            auctions = auctions.filter(
                run__gte=request.GET.get('run_from')
            )

        if request.GET.get('run_to'):
            auctions = auctions.filter(
                run__lte=request.GET.get('run_to')
            )

        if request.GET.get('production_date_from'):
            auctions = auctions.filter(
                production_date__year__gte=request.GET.get('production_date_from')
            )

        if request.GET.get('production_date_to'):
            auctions = auctions.filter(
                production_date__year__lte=request.GET.get('production_date_to')
            )

        if request.GET.get('phrase'):
            auctions = auctions.filter(
                Q(title__icontains=request.GET.get('phrase')) |
                Q(ref_id__icontains=request.GET.get('phrase'))
            )

        return auctions


class AuctionView(View):
    template_name = 'auction.html'

    def get(self, request, pk, title):
        auction = get_object_or_404(Auction, pk=pk)
        photos = auction.photos_list()
        now = datetime.now()

        check = False
        user_accepted = False

        if not auction.published and not request.user.is_superuser:
            return HttpResponse(status=404)

        try:
            max_bet = Bet.objects.filter(accepted=True, auction=auction).latest('price')
        except Bet.DoesNotExist:
            max_bet = None
        
        # auctions available for any user
        #if auction.end_date < timezone.now() and (max_bet and request.user != max_bet.user) and not request.user.is_authenticated:
        #    return HttpResponse(status=404)

        if request.user.is_authenticated:
            try:
                WatchAuction.objects.get(
                    auction__id=auction.id,
                    user=request.user
                )
                auction.observed = True
                check = True
            except WatchAuction.DoesNotExist:
                pass

            try:
                user_ext = UserPrivate.objects.get(user=request.user)
                if user_ext.accepted:
                    user_accepted = True
            except UserPrivate.DoesNotExist:
                try:
                    user_ext = UserBusiness.objects.get(user=request.user)
                    user_accepted = True
                except UserBusiness.DoesNotExist:
                    pass

        end_date = auction.end_date.strftime("%d-%m-%Y %H:%M:%S")
        auction.finish_date = end_date

        if not check:
            auction.observed = False

        is_active = True
        if auction.end_date < timezone.now():
            is_active = False

        prev_offer = None
        if request.user.is_authenticated:
            price = Bet.objects.filter(user=request.user, auction=auction).aggregate(Max('price'))
            if price['price__max']:
                prev_offer = price['price__max']
        return custom_render(
            request,
            self.template_name,
            {'lang': languageManager.get_lang(request.user, request),
             'car': auction, 'photos': photos, 'prev_offer': prev_offer,
             'user_accepted': user_accepted, 'is_active': is_active}
        )


class LoginView(View):
    template_name = 'registration/login.html'

    def post(self, request):
        form = LoginForm(request.POST or None)
        if request.POST and form.is_valid():
            user = form.login(request)
            if user:
                login(request, user)
                return HttpResponseRedirect("/aukcje")

        return custom_render(request, self.template_name, {'form': form, 'lang': languageManager.get_lang(request.user, request)})

    def get(self, request):
        if request.user.is_authenticated:
            return HttpResponseRedirect("/aukcje")

        return custom_render(request, self.template_name, {'lang': languageManager.get_lang(request.user, request)})


@method_decorator(login_required, name='dispatch')
class ChangePasswordView(View):
    template_name = 'account/password.html'

    def post(self, request):
        password1 = request.POST.get('password1', None)
        password2 = request.POST.get('password2', None)

        if password1 != password2:
            return custom_render(request, self.template_name, {'error': 'Podane hasła do siebie nie pasują!'})
        user = request.user
        user_custom = UserPrivate.objects.get(user=user)
        m = hashlib.sha1()
        pass2hash = password1 + user_custom.slug + user_custom.slug
        m.update(pass2hash.encode('UTF-8'))
        user.password = m.hexdigest()
        user.save()

        return custom_render(request, self.template_name, {'success': 'Hasło zmieniono pomyślnie!', 'lang': languageManager.get_lang(request.user, request)})

    def get(self, request):
        return custom_render(request, self.template_name, {'lang': languageManager.get_lang(request.user, request)})


class RemindPasswordView(TemplateView):
    template_name = 'registration/remind.html'
    success_url = '?success=true'

    def get(self, request, token=''):
        if request.user.is_authenticated:
            return HttpResponseRedirect("/aukcje")

        if token == '':
            return custom_render(request, self.template_name)

        try:
            user = UserPrivate.objects.get(token=token)
            return custom_render(request, self.template_name, {'token': 'token'})
        except UserPrivate.DoesNotExist as e:
            return custom_render(request, self.template_name, {'error': 'Link nieprawidłowy!'})

        return custom_render(request, self.template_name, {'error': 'Link nieprawidłowy!'})

    def post(self, request, token=''):
        if request.user.is_authenticated:
            return HttpResponseRedirect("/aukcje")

        if token == '':
            username = request.POST.get('username', '').lower()
            context = {'success': 'Wiadomość została wysłana na podany adres email!'}
            try:
                user = UserPrivate.objects.get(user__email__exact=username)
                user.token = str(binascii.b2a_hex(os.urandom(32)))[2:-1]
                user.token_end_of_validity = datetime.now() + timedelta(hours=24)
                user.save()
                self.send_mail_private(username, user.token)
                return custom_render(request, self.template_name, context)
            except UserPrivate.DoesNotExist as e:
                return custom_render(request, self.template_name, context)
        else:
            password1 = request.POST.get('password1', '')
            password2 = request.POST.get('password2', '')
            if password1 != password2 or len(password1) == 0:
                context = {'error': 'Podane hasła do siebie nie pasują lub nie zostały uzupełnione.', 'token': token}
                return custom_render(request, self.template_name, context)

            try:
                user_custom = UserPrivate.objects.get(token=token)
            except:
                context = {'error': 'Podany link jest nieaktywny. Aby zmienić hasło należy poprosić o zmianę hasła.'}
                return custom_render(request, self.template_name, context)

            if datetime.now() > user_custom.token_end_of_validity:
                context = {'error': 'Ważność linku wygasła. Aby zmienić hasło należy poprosić o ponowną zmianę hasła.'}
                return custom_render(request, self.template_name, context)

            user_custom.token = str(binascii.b2a_hex(os.urandom(32)))[2:-1]
            user_custom.token_end_of_validity = datetime.now()
            user = user_custom.user
            m = hashlib.sha1()
            pass2hash = password1 + user_custom.slug + user_custom.slug
            m.update(pass2hash.encode('UTF-8'))
            user.password = m.hexdigest()
            user.save()
            user_custom.save()

            context = {'success': 'Hasło zostało zaktualizowane pomyślnie, zaloguj się ponownie!'}
            return custom_render(request, self.template_name, context)

    def form_invalid(self, form):
        response = self.form_valid(form)
        return response

    def send_mail_private(self, email, token):
        subject = 'AutaZeSzwajcarii.pl - Przypomnienie hasła'
        message = 'Witamy,<br/>'
        message += 'Właśnie została wysłana prośba o zresetowania hasła w naszym systemie. Aby ustawić nowe hasło, kliknij w poniższy adres URL:<br/>'
        message += '<a href="https://autazeszwajcarii.pl/przypomnij/%s">https://autazeszwajcarii.pl/przypomnij/%s</a><br/><br/>' % (token, token)
        message += 'Link wygaśnie po 24h. Po upływie tego czasu należy wysłać ponowną prośbę o zmianę hasła.<br/>'
        message += 'Jeśli prośba o reset hasła nie została wysłana przez Ciebie, nie klikaj w powyższy link i niezwłocznie skontaktuj się z nami!<br/><br/>'
        message += 'Pozdrawiamy,<br/>Zespół AutaZeSzwajcarii.pl'

        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_NORESPONSE,
                [email],
                html_message=message,
            )
        except Exception as e:
            log_exception(e)

class RegisterView(FormView):
    template_name = 'registration/register.html'
    form_class = RegisterForm
    success_url = '?success=true'

    def get(self, request):
        if request.user.is_authenticated:
            return HttpResponseRedirect("/konto/profil")
        return super().get(self, request, context={'lang': languageManager.get_lang(request.user, request)})

    def post(self, request):
        if request.user.is_authenticated:
            return HttpResponseRedirect("/konto/profil")
        return super().post(self, request, context={'lang': languageManager.get_lang(request.user, request)})

    def form_valid(self, form):
        username = form.cleaned_data.get('email')
        email = username
        password = form.cleaned_data.get('password')

        ret_data = {
            'success': 'False',
            'error_list': list(),
        }
        
        user_exists = User.objects.filter(
            Q(email=email) | Q(username=username) 
        ).exists()

        if user_exists:
            ret_data['error_list'].append('Użytkownik o takim adresie email aktualnie istnieje.')
            return JsonResponse(ret_data)

        slug = str(time()/1000)

        m = hashlib.sha1()
        pass2hash = password + slug + slug
        m.update(pass2hash.encode('UTF-8'))
        pass_hashed = m.hexdigest()

        user = User(
            username=username,
            email=email,
            password=pass_hashed,
        )
        user.save()

        if form.cleaned_data.get('business_name'):
            # create business user here
            user_bus, cr = UserBusiness.objects.get_or_create(
                user=user,
                first_name=form.cleaned_data.get('first_name'),
                second_name=form.cleaned_data.get('second_name'),
                last_name=form.cleaned_data.get('last_name'),
                phone_number=form.cleaned_data.get('phone_number'),
                country=form.cleaned_data.get('country'),
                city_name=form.cleaned_data.get('city_name'),
                postal_code=form.cleaned_data.get('postal_code'),
                street_name=form.cleaned_data.get('street_name'),
                home_number=form.cleaned_data.get('home_number'),
                business_name=form.cleaned_data.get('business_name'),
                nip_code=form.cleaned_data.get('nip_code'),
                note=form.cleaned_data.get('note'),
                slug=slug,
                lang=form.cleaned_data.get('lang'),
                promocode=form.cleaned_data.get('promocode'),
            )

            if not cr:
                user.delete()
                user.save()
                ret_data['error_list'].append('Wystąpił błąd systemu, proszę skontaktować się z administratorem.')
                return JsonResponse(ret_data)

            ret_data['success'] = True
            self.send_mail_business(user_bus)
            return JsonResponse(ret_data)

        else:
            # create private user here
            user_priv, cr = UserPrivate.objects.get_or_create(
                user=user,
                first_name=form.cleaned_data.get('first_name'),
                second_name=form.cleaned_data.get('second_name'),
                last_name=form.cleaned_data.get('last_name'),
                phone_number=form.cleaned_data.get('phone_number'),
                country=form.cleaned_data.get('country'),
                city_name=form.cleaned_data.get('city_name'),
                postal_code=form.cleaned_data.get('postal_code'),
                street_name=form.cleaned_data.get('street_name'),
                home_number=form.cleaned_data.get('home_number'),
                note=form.cleaned_data.get('note'),
                slug=slug,
                lang=form.cleaned_data.get('lang'),
                promocode=form.cleaned_data.get('promocode'),
            )

            # marketing object 
            try:
                campaign = MarketingCampaign.objects.get(cookie_value=self.request.COOKIES.get(MARKETING_SOURCE_COOKIE_NAME, ''))
                user_priv.campaign_source = campaign
                user_priv.save()
            except MarketingCampaign.DoesNotExist:
                pass

            if not cr:
                user.delete()
                user.save()
                ret_data['error_list'].append('Wystąpił błąd systemu, proszę skontaktować się z administratorem.')
                return JsonResponse(ret_data)

            self.send_mail_private(user_priv)
            ret_data['success'] = True
            return JsonResponse(ret_data)

        return super(RegisterView, self).form_valid(form)

    def send_mail_business(self, user):
        subject = 'AutaZeSzwajcarii.pl - zostałeś pomyślnie zarejestrowany'
        message = 'Witaj {},<br/><br/>'.format(user.first_name)
        message += 'Zostałeś pomyślnie zarejestrowany. W ciągu 24h Twoje konto zostanie aktywowane.<br/>'
        message += 'Więcej informacji możesz uzyskać kontaktując się z nami!<br/></br><br/>'
        message += 'Pozdrawiamy,<br/>'
        message += 'Zespół AutaZeSzwajcarii.pl'

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

    def send_mail_private(self, user):
        subject = languageManager.get_trans(user.user, 'email-0')
        message = '{} <br/><br/>'.format(languageManager.get_trans(user.user, 'email-1'))
        message += languageManager.get_trans(user.user, 'email-101')
        message += '<br/>'
        message += languageManager.get_trans(user.user, 'email-102')
        message += '<br/>'
        message += languageManager.get_trans(user.user, 'email-103')
        message += '<br/>'
        message += languageManager.get_trans(user.user, 'email-104')
        message += '<br/>'
        message += languageManager.get_trans(user.user, 'email-105')
        message += '<br/>'
        message += languageManager.get_trans(user.user, 'email-2')
        message += '<br/>'
        message += languageManager.get_trans(user.user, 'email-3')
        message += '<br/><br/>'
        message += languageManager.get_trans(user.user, 'email-4')
        message += '<br/>'
        message += languageManager.get_trans(user.user, 'email-5')
        message += '<br/><br/>Radek Galas,<br/>607 20 70 90'

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


@method_decorator(login_required, name='dispatch')
class AccountView(View):
    template_name = 'account/main.html'

    def get(self, request):
        return custom_render(request, self.template_name, {'lang': languageManager.get_lang(request.user, request)})


@method_decorator(login_required, name='dispatch')
class ProfileView(View):
    template_name = 'account/profile.html'

    def get_user(self, request):
        try:
            user = UserPrivate.objects.get(user=request.user)
            utype = 'Private'
        except UserPrivate.DoesNotExist:
            try:
                user = UserBusiness.objects.get(user=request.user)
                utype = 'Business'
            except UserBusiness.DoesNotExist as e:
                user = None
                utype = None

        return user, utype

    def get(self, request):
        user, utype = self.get_user(request)
        return custom_render(request, self.template_name, {'user2': user, 'type': utype, 'lang': languageManager.get_lang(request.user, request)})


@method_decorator(login_required, name='dispatch')
class LastAuctionsView(View):
    template_name = 'account/last_auctions.html'

    def get(self, request, page=1):
        auctions = Auction.objects.filter(
            bet__user=request.user,
            end_date__gte=datetime.now()-timedelta(days=31),
        ).distinct().order_by('-end_date')
        serializer = AuctionMinSerializer(auctions, many=True)
        paginator = Paginator(serializer.data, settings.PAGE_SIZE)
        page = int(page)
        auctions_ret = list(paginator.page(page))

        paging_to_left = max(1, page-3)
        paging_to_right = min(paginator.num_pages, page+3)

        for i in range(0, len(auctions_ret)):
            auctions_ret[i].link = '/aukcje/licytacja/{}/{}'.format(
                auctions_ret[i]['id'],
                re.sub('[^0-9a-zA-Z]+', '-', auctions_ret[i]['title'].lower())
            )
            end_date = datetime.strptime(auctions_ret[i]['end_date'], "%Y-%m-%dT%H:%M:%S")
            end_date = end_date.strftime("%d-%m-%Y %H:%M:%S")
            auctions_ret[i].finish_date = end_date
            max_bet = Bet.objects.filter(Q(user=request.user) & Q(auction__pk=auctions_ret[i]['id'])).order_by('-price').first()
            auctions_ret[i].bet_price = max_bet.price
            auctions_ret[i].color = max_bet.color

        return custom_render(
            request,
            self.template_name,
            {
                'lang': languageManager.get_lang(request.user, request),
                'auctions': auctions_ret,
                'page': page,
                'max_page': paginator.num_pages,
                'paging_to_left': paging_to_left,
                'paging_to_right': paging_to_right,
             }
        )


@method_decorator(login_required, name='dispatch')
class SearchView(View):
    template_name = 'account/search_auctions.html'

    def get(self, request, page=1):
        tags = WatchTag.objects.filter(user=request.user)

        return custom_render(
            request,
            self.template_name,
            {
                'lang': languageManager.get_lang(request.user, request),
                'tags': tags,
             }
        )


@method_decorator(login_required, name='dispatch')
class ObservedView(View):
    template_name = 'account/observed.html'

    def get(self, request, page=1):
        auctions = Auction.objects.filter(
            watchauction__user=request.user,
            end_date__gte=datetime.now(),
        ).order_by('-end_date')
        serializer = AuctionMinSerializer(auctions, many=True)
        paginator = Paginator(serializer.data, settings.PAGE_SIZE)
        page = int(page)
        auctions_ret = list(paginator.page(page))

        paging_to_left = max(1, page-3)
        paging_to_right = min(paginator.num_pages, page+3)

        auctions_ret2 = list()
        for i in range(0, len(auctions_ret)):
            auctions_ret[i].link = '/aukcje/licytacja/{}/{}'.format(
                auctions_ret[i]['id'],
                re.sub('[^0-9a-zA-Z]+', '-', auctions_ret[i]['title'].lower())
            )
            end_date = datetime.strptime(auctions_ret[i]['end_date'], "%Y-%m-%dT%H:%M:%S")
            end_date = end_date.strftime("%d-%m-%Y %H:%M:%S")
            auctions_ret[i].finish_date = end_date
            max_bet = Bet.objects.filter(Q(user=request.user) & Q(auction__pk=auctions_ret[i]['id'])).order_by('-price').first()
            if max_bet:
                continue
            auctions_ret2.append(auctions_ret[i])

        return custom_render(
            request,
            self.template_name,
            {
                'lang': languageManager.get_lang(request.user, request),
                'auctions': auctions_ret2,
                'page': page,
                'max_page': paginator.num_pages,
                'paging_to_left': paging_to_left,
                'paging_to_right': paging_to_right,
             }
        )


@method_decorator(login_required, name='dispatch')
class WonView(View):
    template_name = 'account/won_auctions.html'

    def get(self, request, page=1):
        # get won bets for current user        
        bets = Bet.objects.filter(user=request.user).order_by('auction__pk', '-price').distinct('auction__pk')
        bets_max = Bet.objects.filter(pk__in=bets).filter(color__in=[1, 2, 5]).values('auction__pk')
        user_auctions = Auction.objects.filter(pk__in=bets_max)

        auctions = list()

        for auction in user_auctions:
            auctions.append(auction)

        auctions = list(set(auctions))
        auctions = sorted(auctions, key=lambda k: k.pk, reverse=True) 
        serializer = AuctionMinSerializer(auctions, many=True)
        paginator = Paginator(serializer.data, settings.PAGE_SIZE)
        page = int(page)
        auctions_ret = list(paginator.page(page))

        paging_to_left = max(1, page-3)
        paging_to_right = min(paginator.num_pages, page+3)
        won = False

        for i in range(0, len(auctions_ret)):
            auctions_ret[i].link = '/aukcje/licytacja/{}/{}'.format(
                auctions_ret[i]['id'],
                re.sub('[^0-9a-zA-Z]+', '-', auctions_ret[i]['title'].lower())
            )
            end_date = datetime.strptime(auctions_ret[i]['end_date'], "%Y-%m-%dT%H:%M:%S")
            end_date = end_date.strftime("%d-%m-%Y %H:%M:%S")
            auctions_ret[i].finish_date = end_date
            max_bet = Bet.objects.filter(Q(user=request.user) & Q(auction__pk=auctions_ret[i]['id'])).order_by('-price').first()
            auctions_ret[i].bet_color = max_bet.color
            auctions_ret[i].bet_price = max_bet.price
            auctions_ret[i].color = max_bet.color
            if max_bet.color == 1 or max_bet.color == 5:
                won = True

        return custom_render(
            request,
            self.template_name,
            {
                'lang': languageManager.get_lang(request.user, request),
                'auctions': auctions_ret,
                'page': page,
                'max_page': paginator.num_pages,
                'paging_to_left': paging_to_left,
                'paging_to_right': paging_to_right,
                'won': won,
             }
        )

