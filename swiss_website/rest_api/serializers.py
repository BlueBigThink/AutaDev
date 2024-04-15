from functools import cmp_to_key

import os
from django.core.files import File
from django.utils.text import slugify

from web_app.utils import log_exception
from rest_framework import serializers
from PIL import Image
from .models import (
    Auction,
    Brand,
    AuctionPhoto,
    Bet,
    TopBet
)


class AuctionMinSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=127,
    )
    production_date = serializers.DateField()
    run = serializers.IntegerField()
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField()
    ref_id = serializers.CharField()
    photos = serializers.FileField(
        source='first_photo',
        max_length=100000,
        allow_empty_file=False,
        use_url=False,
    )
    min_image = serializers.FileField()


class AuctionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=127,
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField()
    data = serializers.JSONField()
    images_count = serializers.IntegerField()
    provider_name = serializers.CharField()
    provider_id = serializers.CharField(max_length=127)
    subprovider_name = serializers.CharField(required=False, max_length=127)
    brand_name = serializers.CharField(required=False,allow_blank=False,max_length=63,source='brand.name')
    production_date = serializers.DateField()
    run = serializers.IntegerField()
    ref_id = serializers.CharField(required=False)
    photos = serializers.ListField(
        source='photos_list',
        child=serializers.FileField(
            max_length=100000,
            allow_empty_file=False,
            use_url=False,
        )
    )

    def create(self, validated_data):
        """
        Create and return a new `Auction` instance, given the validated data.
        """
        brand = validated_data.pop('brand')
        brand, cr = Brand.objects.get_or_create(name=brand['name'])
        images = validated_data.pop('photos_list')

        if len(images) == 0:
            raise Exception('No images for car auction')
            # first_photo = None
            # auction, cr = Auction.objects.get_or_create(brand=brand, **validated_data)
        else:
            # images = sorted(list(images), key=cmp_to_key(img_name_cmp))
            first_photo = images[0]
            image = Image.open(first_photo)
            max_width = 200
            w_scale = image.size[0] / max_width
            height = image.size[1] / w_scale
            result = image.resize((int(max_width), int(height)), Image.ANTIALIAS)
            auction_id = validated_data.get('provider_id', '') + brand.name
            #filename = slugify(auction_id)+'.png'
            filename = slugify(auction_id)+'.jpg'
            result_path = os.path.join('/web_apps/swiss_website/auction_photos/', filename)
            result.save(result_path, format='JPEG')
            with open(result_path, 'rb') as f:
                wrapped_file = File(f)
                auction, cr = Auction.objects.get_or_create(brand=brand, min_image=wrapped_file, **validated_data)
            os.remove(result_path)

        for img in images:
            AuctionPhoto.objects.create(image=img, auction=auction)
        return auction

    def update(self, instance, validated_data):
        """
        Update and return an existing `Auction` instance, given the validated data.
        """
        instance.start_date = validated_data.get('start_date', instance.start_date)
        instance.end_date = validated_data.get('end_date', instance.end_date)
        instance.data = validated_data.get('data', instance.data)
        instance.images_count = validated_data.get('images_count', instance.images_count)
        images = validated_data.pop('photos_list')
        # def img_name_cmp(a, b):
        #     if len(a.name) < len(b.name):
        #         return -1
        #     elif len(a.name) > len(b.name):
        #         return 1

        #     if a.name < b.name:
        #         return -1
        #     elif a.name > b.name:
        #         return 1

        if len(images) == 0:
            raise Exception('No images for car auction')
            # first_photo = None
            # instance.min_image=None
        else:
            # images = sorted(list(images), key=cmp_to_key(img_name_cmp))
            first_photo = images[0]
            image = Image.open(first_photo)
            max_width = 200
            w_scale = image.size[0] / max_width
            height = image.size[1] / w_scale
            result = image.resize((int(max_width), int(height)), Image.ANTIALIAS)
            auction_id = validated_data.get('provider_id', '') + instance.brand.name
            # filename = slugify(auction_id)+'.png'
            filename = slugify(auction_id)+'.jpg'
            result_path = os.path.join('/web_apps/swiss_website/auction_photos/', filename)
            result.save(result_path, format='JPEG')
            instance.min_image = result_path
            # os.remove(result_path)
        
        models_to_delete = AuctionPhoto.objects.filter(auction=instance)
        models_to_delete.delete()
        for img in images:
            AuctionPhoto.objects.create(image=img, auction=instance)
        instance.save()
        # update bet, scheduledbet
        try:
            bet = Bet.objects.get(auction_id=instance.id)
            bet.auction_end_date = instance.end_date
            bet.save()
            topbet = TopBet.objects.get(auction_id=instance.id)
            topbet.auction_end_date = instance.end_date
            topbet.save()
        except:
            pass
        return instance


class AuctionMinExternalSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=127,
    )
    production_date = serializers.DateField()
    run = serializers.IntegerField()
    end_date = serializers.DateTimeField()
    ref_id = serializers.CharField()


class AuctionExternalSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=127,
    )
    end_date = serializers.DateTimeField()
    data = serializers.JSONField()
    provider_name = serializers.CharField()
    provider_id = serializers.CharField(max_length=127)
    subprovider_name = serializers.CharField(required=False, max_length=127)
    brand_name = serializers.CharField(required=False,allow_blank=False,max_length=63,source='brand.name')
    production_date = serializers.DateField()
    run = serializers.IntegerField()
    ref_id = serializers.CharField(required=False)
    photos = serializers.ListField(
        source='photos_list',
        child=serializers.FileField(
            max_length=100000,
            allow_empty_file=False,
            use_url=False,
        )
    )