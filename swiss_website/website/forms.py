import hashlib
from django import forms
from django.forms import ModelForm
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from rest_api.models import (
    UserPrivate,
    UserBusiness,
)


class RegisterForm(ModelForm):
    email = forms.CharField(max_length="255")
    password = forms.CharField(max_length="255")

    class Meta:
        model = UserBusiness
        fields = ['first_name', 'note', 'second_name', 'last_name', 'country', 'postal_code', 'street_name', 'city_name', 'home_number', 'business_name', 'nip_code', 'email', 'phone_number', 'password', 'lang', 'promocode']


class ChangePasswordForm(forms.Form):
    password2 = forms.CharField(widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(widget=forms.PasswordInput, required=True)


class LoginForm(forms.Form):
    username = forms.CharField(max_length=255, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        user = self.authenticate(username=username, password=password)
        if not user or not user.is_active:
            raise forms.ValidationError("Sorry, that login was invalid. Please try again.")
        return self.cleaned_data

    def login(self, request):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        user = self.authenticate(username=username, password=password)
        return user

    def authenticate(self, username=None, password=None):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None

        flag = False

        try:
            user_custom = UserPrivate.objects.get(user=user)
            flag = True
        except UserPrivate.DoesNotExist:
            flag = False

        if not flag:
            try:
                user_custom = UserBusiness.objects.get(user=user)
                flag = True
            except UserBusiness.DoesNotExist:
                flag = False

        if not flag:
            return None

        m = hashlib.sha1()
        pass2hash = password + user_custom.slug + user_custom.slug
        m.update(pass2hash.encode('UTF-8'))

        if m.hexdigest() == user.password:
            return user

        return None
