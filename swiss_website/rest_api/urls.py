from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns
from .views import (
    AuctionList,
    AuctionDetails,
    AddToObserved,
    StopObserveView,
    BetView,
    SearchAddView,
    SearchRemoveView,
    PublishView,
    ExternalAuctionList,
    ExternalAuctionDetails,
)

urlpatterns = [
    # For external companies
    url('^external/scc/$', ExternalAuctionList.as_view()),
    url('^external/scc/(?P<pk>[0-9]+)/$', ExternalAuctionDetails.as_view()),
    # End of external companies
    url('^auctions/$', AuctionList.as_view()),
    url('^auctions/(?P<pk>[0-9]+)/$', AuctionDetails.as_view()),
    url('^obserwuj/$', AddToObserved.as_view()),
    url('^nieobserwuj/$', StopObserveView.as_view()),
    url('^opublikuj/$', PublishView.as_view()),
    url('^licytuj/$', BetView.as_view()),
    url('^poszukiwane/dodaj/$', SearchAddView.as_view()),
    url('^poszukiwane/usun/$', SearchRemoveView.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns)
