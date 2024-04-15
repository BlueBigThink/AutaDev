from django.db.models.expressions import Subquery
from django.forms import TextInput, Textarea
from django.db import models
from datetime import datetime
from django.contrib.admin import widgets
from django.contrib.admin.sites import site
from django.contrib.admin.widgets import ForeignKeyRawIdWidget
from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry, DELETION
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.html import escape
from django.core.urlresolvers import reverse
from django.db.models import F, Max, Q, Count, OuterRef, Subquery
from django.conf.urls import url
from django_admin_json_editor import JSONEditorWidget
from django.contrib.admin.views.main import ChangeList
from urllib.parse import quote

from web_app.utils import log_exception
from .models import (
    Auction,
    TopAuction,
    AuctionPhoto,
    UserPrivate,
    UserBusiness,
    Bet,
    BetSupervisor,
    LanguageModel,
    AutomateDashboardModel,
    ShortUrlModel,
    ScheduledBet,
    Banner,
    MarketingCampaign,
    BetNotificationsModel,
    TopBet
)

from .views import (LanguageAdminView, AutomateDashboardAdminView, BetNotificationsAdminView)

from django.contrib.auth.models import User
# from django.contrib.sites.models import Site
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
class DefaultAdmin(admin.ModelAdmin):
    pass


class LogEntryAdmin(admin.ModelAdmin):
    list_display = [
        'action_time',
        'user',
        'content_type',
        'change_message',
        'object_repr',
    ]
    list_filter = [
        'user',
        'content_type',
        'object_repr',
    ]

'''
    date_hierarchy = 'action_time'
    readonly_fields = LogEntry._meta.get_all_field_names()
    search_fields = [
        'object_repr',
        'change_message'
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.method != 'POST'

    def has_delete_permission(self, request, obj=None):
        return False

    def action_flag_(self, obj):
        flags = {
            1: "Addition",
            2: "Changed",
            3: "Deleted",
        }
        return flags[obj.action_flag]

    def object_link(self, obj):
        if obj.action_flag == DELETION:
            link = escape(obj.object_repr)
        else:
            ct = obj.content_type
            link = u'<a href="%s">%s</a>' % (
                reverse('admin:%s_%s_change' % (ct.app_label, ct.model), args=[obj.object_id]),
                escape(obj.object_repr),
            )
        return link
    object_link.allow_tags = True
    object_link.admin_order_field = 'object_repr'
    object_link.short_description = u'object'

'''

class ScheduledBetAdmin(admin.ModelAdmin):
    raw_id_fields = ('bet', 'topbet')
    list_display = ('name', 'topbet_id', 'auction_price', 'price', 'price_max', 'betted', 'auction_to_end')
    readonly_fields = ('betted',)
    list_per_page = 100
    list_select_related = ('topbet__user', 'topbet__auction', 'bet__auction', 'bet__user_priv')
    exclude = ('bet', )
    ordering = ('-topbet__auction_end_date', )
    def lookup_allowed(self, key):
        if key in ('auction__end_date__gte', 'auction__end_date', 'auction__subprovider_name', 'auction__subprovider_name__in'):
            return True
        return super(ScheduledBetAdmin, self).lookup_allowed(key)

    def lookup_allowed(self, key, value):
        if key in ('auction__end_date__gte', 'auction__end_date', 'auction__subprovider_name', 'auction__subprovider_name__in'):
            return True
        return super(ScheduledBetAdmin, self).lookup_allowed(key, value)

    def save_model(self, request, obj, form, change):
        topbet = TopBet.objects.get(id=obj.topbet_id)
        topbet.scheduled = True
        topbet.save()
        super().save_model(request, obj, form, change)

    def name(self, obj):
        user = None
        link = ""
        try:
            user = '%s %s' % (obj.topbet.user.first_name, obj.topbet.user.last_name)
            link = '%s %s' % (obj.topbet.auction.title, user)
        except:
            pass
        try:
            user = '%s %s' % (obj.bet.user_priv.first_name, obj.bet.user_priv.last_name)
            link = '%s %s' % (obj.bet.auction.title, user)
        except :
            pass
        return link
    name.description = "Licytacja"

    def auction_price(self, obj):
        print(obj)
        return obj.bet.price
    auction_price.short_description = "Cena uż. [CHF]"

    def auction_to_end(self, obj):
        return obj.bet.auction.to_end_date()
    auction_to_end.allow_tags = True
    auction_to_end.short_description = 'Do końca'


class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'published',)
    list_editable = ('published', )


class ShortUrlAdmin(admin.ModelAdmin):
    list_display = ('title', 'short_url',)
    readonly_fields = ('short_url',)


class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(BetNotificationsModel)
class BetNotificationsAdmin(admin.ModelAdmin):
    def get_urls(self):
        view_name = '{}_{}_changelist'.format(
                BetNotificationsModel._meta.app_label, BetNotificationsModel._meta.model_name)
        return [
            url(r'^bet-notifications/$', BetNotificationsAdminView.as_view(), name=view_name)
        ]


@admin.register(LanguageModel)
class LanguageAdmin(admin.ModelAdmin):
    def get_urls(self):
        view_name = '{}_{}_changelist'.format(
                LanguageModel._meta.app_label, LanguageModel._meta.model_name)
        return [
            url(r'^languages/$', LanguageAdminView.as_view(), name=view_name)
        ]

@admin.register(AutomateDashboardModel)
class AutomateDashboardAdmin(admin.ModelAdmin):
    def get_urls(self):
        view_name = '{}_{}_changelist'.format(
                AutomateDashboardModel._meta.app_label, AutomateDashboardModel._meta.model_name)
        return [
            url(r'^automatedashboard/$', AutomateDashboardAdminView.as_view(), name=view_name),
            url(r'^automatedashboard/(?P<provider>\w+)/changepass/$', AutomateDashboardAdminView.as_view(), name=view_name)
        ]

def make_published(modeladmin, request, queryset):
    queryset.update(published=True)
make_published.short_description = "Oznacz jako opublikowane"


def make_unpublished(modeladmin, request, queryset):
    queryset.update(published=False)
make_unpublished.short_description = "Oznacz jako nieopublikowane"


def set_top_auction(modeladmin, request, queryset):
    for car in queryset:
        top = TopAuction(auction=car)
        top.save()
set_top_auction.short_description = "Ustaw jako aukcje dnia"


class ArchiveAuctionListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _('Archiwum')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ('yes', _('Aktywne')),
            ('no', _('Archiwum')),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value() == 'yes':
            return queryset.filter(end_date__gte=timezone.now()).order_by('-end_date')
        elif self.value() == 'no':
            return queryset.filter(end_date__lt=timezone.now()).order_by('end_date')
        else:
            return queryset.order_by('-end_date')


class ColorAuctionListFilter(admin.SimpleListFilter):
    title = _('Kolor')
    parameter_name = 'color'

    def lookups(self, request, model_admin):
        return (
            ('0', _('Biały')),
            ('1', _('Zielony')),
            ('2', _('Niebieski')),
            ('3', _('Pomarańczowy')),
            ('4', _('Czerwony')),
            ('5', _('Złoty')),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        color = int(self.value())
        bets = Bet.objects.order_by('auction__pk', '-price').distinct('auction__pk')
        bets_max = Bet.objects.filter(pk__in=bets).filter(color=color).values('auction__pk')
        ret_queryset = queryset.filter(pk__in=bets_max)

        return ret_queryset


class AuctionPhotoAdmin(admin.StackedInline):
    model = AuctionPhoto


def dynamic_schema(widget):
    return {
        "type": "object",
    }



class AuctionAdmin(admin.ModelAdmin):
    list_display = ('title', 'ref_id', 'published', 'highlighted', 'first_photo_img', 'provider_name', 'brand', 'to_end_date', 'get_bets')
    readonly_fields = ('first_photo_img', 'ref_id', 'get_bets',)
    list_editable = ('published', 'highlighted',)
    list_per_page = 30
    list_filter = (ArchiveAuctionListFilter, 'provider_name', ColorAuctionListFilter,)
    search_fields = ('title', 'id', 'ref_id', 'provider_id', 'data')
    actions = (make_published, make_unpublished, set_top_auction, )
    inlines = (AuctionPhotoAdmin, )
    exclude = ('images_count', 'min_image', 'ref_id', 'get_bets', )
    # list_select_related = ('brand', )
    def get_queryset(self, request):
        queryset = super(AuctionAdmin, self).get_queryset(request)
        return queryset.select_related('brand',)


    def get_form(self, request, obj=None, **kwargs):
        widget = JSONEditorWidget(dynamic_schema, False)
        form = super().get_form(request, obj, widgets={'data': widget}, **kwargs)
        return form


class ColorBetListFilter(admin.SimpleListFilter):
    title = _('Kolor')
    parameter_name = 'color'

    def lookups(self, request, model_admin):
        if request.user.groups.filter(name='RestrictedGroup').exists():
                 return (
                ('1', _('Zielony')),
                ('2', _('Niebieski')),
            )
        else:
            return (
                ('0', _('Biały')),
                ('1', _('Zielony')),
                ('2', _('Niebieski')),
                ('3', _('Pomarańczowy')),
                ('4', _('Czerwony')),
                ('5', _('Złoty')),
            )

    def queryset(self, request, queryset):
        if self.value() is None:
            if request.user.groups.filter(name='RestrictedGroup').exists():
                return queryset.filter(color__in=[1, 2])
            else:
                return queryset
        color = int(self.value())
        ret_queryset = queryset.filter(color=color)
        return ret_queryset

class BetActiveFilter(admin.SimpleListFilter):
    title = _('Aktywne')
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        if request.user.groups.filter(name='RestrictedGroup').exists():
            return (
                ('no', _('Nie')),
                ('yes', _('Tak')),
            )
        else:
            return (
                ('yes', _('Tak')),
                ('no', _('Nie')),
            )

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == str(lookup),
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }

    def queryset(self, request, queryset):
        query = self.value()
        if query == 'no':
            queryset = queryset.filter(auction_end_date__lt=timezone.now()).order_by('-auction_end_date')
        elif query == 'yes':
            queryset = queryset.filter(auction_end_date__gt=timezone.now()).order_by('auction_end_date')
        else:
            if request.user.groups.filter(name='RestrictedGroup').exists():
                queryset = queryset.filter(auction_end_date__lt=timezone.now()).order_by('-auction_end_date')
            else:
                queryset = queryset.filter(auction_end_date__gt=timezone.now()).order_by('auction_end_date')
        return queryset

class TopBetAdmin(admin.ModelAdmin):
    raw_id_fields = ('auction', 'user')
    search_fields = ('auction__ref_id', 'auction__title', 'user__email', 'user__id',)
    list_filter = (ColorBetListFilter, BetActiveFilter)
    list_per_page = 100
    list_display = ('auction', 'auction_link', 'color',)
    list_editable = ('color',)
    list_select_related = ('auction', 'user__user', 'bet')
    exclude=('auction_end_date', 'bet', 'bet_count')
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':2, 'cols':40})},
    }
    
    def get_list_display(self, request):
        if request.user.groups.filter(name='RestrictedGroup').exists():
            return ('auction', 'auction_link', 'user_info', 'price', 'note_admin', 'scheduled', 'auction_to_end', 'color',)
        else:
            return ('auction', 'auction_link', 'user_link', 'price', 'note_admin', 'scheduled', 'auction_to_end', 'color',)

    def auction_link(self, obj):
        try:
            bet_link = f'<a href="{obj.auction.get_bets_link()}" style="color:#ac0303;float:right;margin-right:5px">({obj.bet_count})</a>'
            provider_link = f'<a href="{obj.auction.get_provider_link()}" target="_blank" style="float:right">{obj.auction.provider_name}</a>'
            auction_link = f'<a target="_blank" class="admin-auction-short-link" href="{obj.auction.get_link()}">Podgląd aukcji</a>'
            return auction_link + provider_link + bet_link
        except:
            return "Błąd linku"
    auction_link.short_description = 'Link do aukcji'
    auction_link.allow_tags = True

    # user field for normal stuff
    def user_link(self, obj):
        try:
            user_bets_link = f'<a href="/admin/rest_api/bet/?q={obj.user.user.email}" style="color:#ac0303;float:right;display:inline-block">licytacje</a>'
            user_name = f'<a href="/admin/rest_api/userprivate/{obj.user.id}/change/" style="display:inline-block;float:left;">{obj.user.first_name} {obj.user.last_name}</a>'
            return user_name + user_bets_link
        except:
            return obj.user.username
    user_link.short_description = 'Użytkownik'
    user_link.allow_tags = True

    # user field for restricted user
    def user_info(self, obj):
        try:
            user_bets_link = f'<a href="/admin/rest_api/bet/?q={obj.user.email}" style="color:#ac0303;float:right;display:inline-block">licytacje</a>'
            user_name = f'<span style="display:inline-block;float:left;">{obj.user.first_name} {obj.user.last_name}</span>'
            return user_name + user_bets_link
        except:
            return obj.user.username
    user_info.short_description = 'Użytkownik'
    user_info.allow_tags = True

    def auction_to_end(self, obj):
        return obj.auction.to_end_date()
    auction_to_end.allow_tags = True
    auction_to_end.short_description = 'Do końca'

    def note_admin(self, obj):
        note = '<span style="float:left" class="admin-auction-short-note">' + obj.bet.note + '</span>'
        return note
    note_admin.allow_tags = True
    note_admin.short_description = 'Notka'

    def lookup_allowed(self, key):
        if key in ('auction_end_date__gte', 'auction_end_date', ):
            return True
        return super().lookup_allowed(key)

    def lookup_allowed(self, key, value):
        if key in ('auction_end_date__gte', 'auction_end_date', ):
            return True
        return super().lookup_allowed(key, value)
    
    def save_model(self, request, obj, form, change):
        print(obj.bet, obj.note, obj.bet_id)
        bet = Bet.objects.get(id=obj.bet_id)
        bet.note = obj.note
        bet.save()
        super().save_model(request, obj, form, change)
    # def get_search_results(self, request, queryset, search_term):
    #     queryset, use_distinct = super(TopBetAdmin, self).get_search_results(request, queryset, search_term)
    #     ret_queryset = queryset.select_related('auction', 'user', 'bet')
    #     return ret_queryset, use_distinct

class BetAdmin(admin.ModelAdmin):
    raw_id_fields = ('auction', 'user')
    search_fields = ('auction__ref_id', 'user__email', 'auction__title', 'user__id',)
    list_display = ('auction', 'auction_link')
    # list_editable = ('color',)
    list_select_related = ('auction', 'user', 'user_priv')
    exclude=('user_priv', 'auction_end_date', 'note', 'color')
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':2, 'cols':40})},
    }
    ordering = ('-auction_end_date', '-price')
    def get_list_display(self, request):
        if request.user.groups.filter(name='RestrictedGroup').exists():
            return ('auction', 'auction_link', 'user_info', 'price', 'note_admin', 'auction_to_end')
        else:
            return ('auction', 'auction_link', 'user_link', 'price', 'note_admin', 'auction_to_end')

    def auction_to_end(self, obj):
        return obj.auction.to_end_date()
    auction_to_end.allow_tags = True
    auction_to_end.short_description = 'Do końca'
    
    def end_date(self, obj):
        return obj.auction.end_date
    
    def note_admin(self, obj):
        note = '<span style="float:left" class="admin-auction-short-note">' + obj.note + '</span>'
        return note
    note_admin.allow_tags = True
    note_admin.short_description = 'Notka'

    def auction_link(self, obj):
        try:
            provider_link = '<a href="%s" target="_blank" style="float:right">%s</a>' % (obj.auction.get_provider_link(), obj.auction.provider_name)
            auction_link = '<a target="_blank" class="admin-auction-short-link" href="%s">Podgląd aukcji</a> ' % obj.auction.get_link()
            # if obj.auction.get_provider_link() is not None:
            #     link += provider_link
            # else:
            #     link += '<span style="float:right">%s</span>' % obj.auction.provider_name
            return auction_link + provider_link
        except Exception as e:
            log_exception(e)
            return "Błąd linku"
    auction_link.allow_tags = True
    auction_link.short_description = 'Link do aukcji'

    def user_link(self, obj):
        try:
            user_bets_link = f'<a href="/admin/rest_api/bet/?q={obj.user.email}" style="color:#ac0303;float:right;display:inline-block">licytacje</a>'
            user_name = f'<a href="/admin/rest_api/userprivate/{obj.user_priv.id}/change/" style="display:inline-block;float:left;">{obj.user_priv.first_name} {obj.user_priv.last_name}</a>'
            return user_name + user_bets_link
        except:
            return obj.user.username
    user_link.short_description = 'Użytkownik'
    user_link.allow_tags = True

    # user field for restricted user
    def user_info(self, obj):
        try:
            user_bets_link = f'<a href="/admin/rest_api/bet/?q={obj.user.email}" style="color:#ac0303;float:right;display:inline-block">licytacje</a>'
            user_name = f'<span style="display:inline-block;float:left;">{obj.user_priv.first_name} {obj.user_priv.last_name}</span>'
            return user_name + user_bets_link
        except:
            return obj.user.username
    user_info.short_description = 'Użytkownik'
    user_info.allow_tags = True

    def lookup_allowed(self, key):
        if key in ('auction__end_date__gte', 'auction__end_date', ):
            return True
        return super().lookup_allowed(key)

    def lookup_allowed(self, key, value):
        if key in ('auction__end_date__gte', 'auction__end_date', ):
            return True
        return super().lookup_allowed(key, value)
    

class BetSupervisorAdmin(admin.ModelAdmin):
    raw_id_fields = ('auction',)
    list_display = ('auction_link', 'user_registered', 'price', 'auction_to_end', 'color',)
    #readonly_fields = ('user',)

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':2, 'cols':40})},
    }

    def get_readonly_fields(self, request, obj=None):
        if obj: #This is the case when obj is already created i.e. it's an edit
            return ('user', )
        else:
            return []

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super(BetSupervisorAdmin, self).get_search_results(request, queryset, search_term)
        current_user = UserPrivate.objects.get(user=request.user)
        managed_priv_users = UserPrivate.objects.filter(user_top=current_user)
        managed_users = [us.user for us in managed_priv_users]
        queryset = queryset.filter(user__in=managed_users)

        user_private = None
        last_name = 'NOTEXISTENTLASTNAME'
        splitted = search_term.split(' ')
        first_name = splitted[0]
        if len(splitted) > 1:
            last_name = splitted[1]
        try:
            user_private = UserPrivate.objects.filter(
                Q(user__email__icontains=search_term) |
                Q(Q(first_name__icontains=first_name) &
                    Q(last_name__icontains=last_name)) |
                Q(last_name__icontains=search_term)
            ).first()
        except UserPrivate.DoesNotExist:
            pass

        user_business = None
        try:
            user_business = UserBusiness.objects.get(user__email__icontains=search_term)
        except UserBusiness.DoesNotExist:
            pass

        user = user_private
        if user_business:
            user = user_business

        if not user:
            return queryset, use_distinct

        managed_users.append(user.user)
        bets = BetSupervisor.objects.filter(user__in=managed_users)
        queryset |= bets

        if request.GET.get('q', None) is not None and request.GET.get('q', None):
            ret_queryset = queryset.order_by('auction', '-price').distinct('auction')

            queryset_low = queryset.filter(id__in=ret_queryset, auction__end_date__gt=timezone.now())
            queryset_high = queryset.filter(id__in=ret_queryset, auction__end_date__lt=timezone.now())

            ret_queryset = queryset.extra(
                 select={
                     'is_recent': "CASE WHEN \"rest_api_auction\".\"end_date\" < '%s' THEN '01-01-2037' ELSE \"rest_api_auction\".\"end_date\" END" % timezone.now(), 
                     'is_recent2': "CASE WHEN \"rest_api_auction\".\"end_date\" > '%s' THEN '01-01-1970' ELSE \"rest_api_auction\".\"end_date\" END" % timezone.now(), 
                 }).order_by('is_recent', '-is_recent2', '-price')

            return ret_queryset, use_distinct

        return queryset, use_distinct

    def get_queryset(self, request):
        queryset = super(BetSupervisorAdmin, self).get_queryset(request)
        current_user = UserPrivate.objects.get(user=request.user)
        managed_priv_users = UserPrivate.objects.filter(user_top=current_user)
        managed_users = [us.user for us in managed_priv_users]
        queryset = queryset.filter(user__in=managed_users)

        if '@' in request.GET.get('q', ''):
            return queryset

        ret_queryset = None
        if request.build_absolute_uri().endswith('admin/rest_api/bet/'):
            ret_queryset = queryset.order_by('auction', '-price').distinct('auction')
        else:
            ret_queryset = queryset

        queryset_low = queryset.filter(id__in=ret_queryset, auction__end_date__gt=timezone.now());
        queryset_high = queryset.filter(id__in=ret_queryset, auction__end_date__lt=timezone.now());

        ret_queryset = queryset_low | queryset_high
        # ret_queryset = ret_queryset.extra(select={'is_recent': "\"rest_api_auction\".\"end_date\" < '%s'" % timezone.now()}).order_by('is_recent', 'auction__end_date')
        ret_queryset = ret_queryset.extra(
             select={
                 'is_recent': "CASE WHEN \"rest_api_auction\".\"end_date\" < '%s' THEN '01-01-2037' ELSE \"rest_api_auction\".\"end_date\" END" % timezone.now(), 
                 'is_recent2': "CASE WHEN \"rest_api_auction\".\"end_date\" > '%s' THEN '01-01-1970' ELSE \"rest_api_auction\".\"end_date\" END" % timezone.now(), 
             }).order_by('is_recent', '-is_recent2', '-price')

        return ret_queryset

class AuctionPhotoAdmin(admin.ModelAdmin):
    pass


class UserAdmin(admin.ModelAdmin):
    raw_id_fields = ('user_top',)
    list_display = ('first_name', 'last_name', 'phone_number', 'email', 'accepted', 'note', 'bets', )
    list_per_page = 30
    list_editable = ('accepted', )
    search_fields = ('first_name', 'last_name', 'phone_number', 'lookup',)


class UserBusinessAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'second_name', 'business_name', 'phone_number', 'email', 'accepted', 'note', 'bets', )
    list_per_page = 30
    search_fields = ('first_name', 'second_name', 'phone_number', 'business_name', )
    list_editable = ('accepted', )


class TopAuctionAdmin(admin.ModelAdmin):
    list_display = ('get_title', 'get_photo_auction', 'admin_link', 'get_end_date', )


admin.site.register(Auction, AuctionAdmin)
admin.site.register(TopAuction, TopAuctionAdmin)
# admin.site.register(AuctionPhoto, DefaultAdmin)
admin.site.register(UserPrivate, UserAdmin)
# admin.site.register(UserBusiness, UserBusinessAdmin)
admin.site.register(Bet, BetAdmin)
admin.site.register(TopBet, TopBetAdmin)
admin.site.register(BetSupervisor, BetSupervisorAdmin)
admin.site.register(ShortUrlModel, ShortUrlAdmin)
admin.site.register(ScheduledBet, ScheduledBetAdmin)
admin.site.register(Banner, BannerAdmin)

#admin.site.unregister(User)
#admin.site.unregister(Group)
#admin.site.unregister(Site)
#admin.site.unregister(Token)
admin.site.register(LogEntry, LogEntryAdmin)
admin.site.register(MarketingCampaign, MarketingCampaignAdmin)
        