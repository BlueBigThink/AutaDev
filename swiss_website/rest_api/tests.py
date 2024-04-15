import json
from django.test import TestCase
from django.contrib.auth.models import User
from .models import Auction
import requests
from  .views import AuctionList

from django.test import TestCase, RequestFactory
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token


class AccountTests(TestCase):
    def test_auction_creation_with_image(self):
        # usr = User.objects.create_superuser('owni', 'email@email.eu', 'qwerty123')
        # url = 'http://localhost:8000/api/v1/auctions/'
        # self.client.login(username='owni', password='qwerty123')
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            username='test', email='test@test.te', password='test'
        )
        token = Token(user=self.user)
        token.save()

        data = {
            "id": 1,
            "title": "Sprzedam Opla Updated",
            "start_date": "2017-03-21 14:30:59",
            "end_date": "2017-03-21 14:30:59",
            "data": json.dumps({'id': 145}),
            "images_count": 5,
            "provider_name": "axa",
            "provider_id": "adsasewq33331ef",
            "brand_name": "Opel",
            "production_date": "2017-03-21",
            "run": 230005,
        }
        files = [
            ('a.img', open("tests_static/cheetah.jpg", "rb")),
            ('b.img', open("tests_static/cheetah.jpg", "rb")),
        ]
        # headers = {
        #     'Authorization': 'Token ' + token.key
        # }

        request = self.factory.post('/api/v1/auctions/', data=data, HTTP_AUTHORIZATION='Token ' + token.key)
        request.user = self.user

        response = AuctionList.as_view()(request)
        print(response)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
