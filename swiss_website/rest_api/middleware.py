from datetime import timedelta, datetime
from django.utils.deprecation import MiddlewareMixin
from rest_api.models import MarketingCampaign
from web_app.settings import MARKETING_SOURCE_COOKIE_NAME


class CampaignTrackingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        current_val = request.COOKIES.get(MARKETING_SOURCE_COOKIE_NAME, None)
        if current_val:
            return response
        url = request.build_absolute_uri()
        http_ref = request.META.get('HTTP_REFERER', '')
        campaigns = MarketingCampaign.objects.all()
         
        ref_cookie_value = None
        for cam in campaigns:
            if cam.url_string in url or cam.url_string in http_ref:
                ref_cookie_value = cam.cookie_value
                break

        if not ref_cookie_value:
            return response

        max_age = 365 * 24 * 60 * 60  # 10 years
        expires = datetime.utcnow() + timedelta(seconds=max_age)
        response.set_cookie(
            MARKETING_SOURCE_COOKIE_NAME,
            ref_cookie_value,
            expires=expires.utctimetuple(), 
            max_age=max_age
        )

        return response
