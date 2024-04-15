import logging
import re
from django.core.mail import send_mail, BadHeaderError
#from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from rest_api.models import UserPrivate, UserBusiness

from web_app.language_manager import LanguageManager
from web_app.utils import log_exception
from django.conf import settings
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sends emails to ALL active users about last changes'

    def handle(self, *args, **options):
        private_users = UserPrivate.objects.all()
        business_users = UserBusiness.objects.all()
        users = list(private_users) + list(business_users)

        for user in users:

            if user.user.is_active == True:
            	self.send_email(user, user.user.email)

    def send_email(self, user, user_email):
        language_manager = LanguageManager()
        subject = 'Ważna informacja od właściciela portalu AutaZeSzwajcarii.pl'
#        message = '{} {},<br/><br/>'.format(language_manager.get_trans(user.user, 'email-7'), user.first_name)
        message = 'Dzień dobry :)\r\n\r\nSzanowni Państwo,\r\n\r\njak zapewne zauważyliście, zaktualizowaliśmy dane kontaktowe firmy i pracowników obsługi na portalu AutaZeSzwajcarii.pl.\r\n\r\nKonta Klientów, historia, warunki współpracy oraz indywidualne ustalenia pozostają bez zmian\r\ni są na tych samych zasadach. Kształt i funkcje portalu nie zmieniają się.\r\n\r\nAktualne dane kontaktowe to:\r\n500 224 555, biuro@autazeszwajcarii.pl - biuro/infolinia\r\n607 20 70 90, dobre@autazeszwajcarii.pl - Radek, właściciel\r\n\r\nZmianom organizacyjnym towarzyszą także zmiany w składzie osobowym pracowników\r\ni współpracowników. Rozstałem się z osobami, które znam i darzyłem zaufaniem,\r\na które dopuściły się czynów, które wypełniają znamiona nieuczciwej konkurencji.\r\n\r\nWśród osób, z którymi się rozstałem są moi byli pracownicy:\r\nPaweł S.,\r\nKrzysztof P.,\r\nMariusz K.\r\ni osoby współpracujące:\r\nDamian S.,\r\nDominik S.,\r\nKrzysztof P.\r\n\r\nWyżej wymienieni nie pracują już ze mną i nie są uprawnieni do kontaktu z Państwem, sprzedaży pojazdów i reprezentowania firmy oraz portalu AutaZeSzwajcarii.pl.\r\nW ich miejsce do zespołu AutaZeSzwajcarii.pl dołączyły nowe osoby.\r\n\r\nDecyzje o zmianie organizacyjnej i zmianach w składzie osobowym podyktowane są koniecznością ochrony Państwa i moich interesów.\r\n\r\nPrzy tej okazji chciałbym stanowczo zaprzeczyć przekazywanym Państwu informacjom. Oświadczam, że AutaZeSzwajcarii.pl jest portalem, którego byłem i jestem jedynym właścicielem. Nie planuję sprzedaży portalu, firmy, ograniczenia jej działalności czy dzielenia podmiotu - niezmiennie pozostaję wyłącznym właścicielem firmy i portalu aukcyjnego.\r\n\r\n\r\nAktualne informacje o firmie i jej właścicielu oraz numerach telefonów oraz adresach e-mail znajdziecie Państwo na naszej stronie internetowej autazeszwajcarii.pl/kontakt i stronie w portalu facebook.com.\r\n\r\n\r\nZespół AutaZeSzwajcarii.pl, w nowym składzie, jest do Waszej dyspozycji pod numerem infolinii i niezmiennie numerem właściciela.\r\n\r\n\r\nNasze aktualne numery telefonów i adresy e-mail:\r\n500 224 555, biuro@autazeszwajcarii.pl biuro/infolinia\r\n607 20 70 90, dobre@autazeszwajcarii.pl Radek (właściciel)\r\n\r\n\r\nDziękuję za uwagę. Pozdrawiam serdecznie i zapraszam do współpracy,\r\n\r\nRadosław Galas\r\nwłaściciel\r\nautazeszwajcarii.pl\r\n\r\nPodmiot odpowiedzialny:\r\nGALERIA OTWOCK GRAFFITI RADOSŁAW GALAS\r\n05-400 Otwock Ul. Świderska 13'
        htmlmessage = 'Dzień dobry :)<br/><br/>Szanowni Państwo,<br/><br/>jak zapewne zauważyliście, zaktualizowaliśmy dane kontaktowe firmy i pracowników obsługi na portalu <a href="https://autazeszwajcarii.pl">AutaZeSzwajcarii.pl</a>.<br/><h4>Konta Klientów, historia, warunki współpracy oraz indywidualne ustalenia pozostają bez zmian<br/>i są na tych samych zasadach. Kształt i funkcje portalu nie zmieniają się.</h4>Nasze <b>AKTUALNE</b> numery telefonów i adresy e-mail to:<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>500 224 555</b>, biuro@autazeszwajcarii.pl - biuro/infolinia<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>607 20 70 90</b>, dobre@autazeszwajcarii.pl - Radek, właściciel<br/><br/><br/>Zmianom organizacyjnym towarzyszą także zmiany w składzie osobowym pracowników<br/>i współpracowników. Rozstałem się z osobami, które znam i darzyłem zaufaniem,<br/>a które dopuściły się czynów, które wypełniają znamiona nieuczciwej konkurencji.<br/><br/>Wśród osób, z którymi się rozstałem są moi <b>byli pracownicy:</b><br/><br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>Paweł S.</b>,<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>Krzysztof P.</b>,<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>Mariusz K.</b><br/>&nbsp;&nbsp;&nbsp;&nbsp;i osoby współpracujące:<br/>&nbsp;&nbsp;&nbsp;&nbsp;Damian S.,<br/>&nbsp;&nbsp;&nbsp;&nbsp;Dominik S.,<br/>&nbsp;&nbsp;&nbsp;&nbsp;Krzysztof P.<br/><br/><br/><b>Wyżej wymienieni nie pracują już</b> ze mną i nie są uprawnieni do kontaktu z Państwem, sprzedaży pojazdów i reprezentowania firmy oraz portalu <a href="https://autazeszwajcarii.pl">AutaZeSzwajcarii.pl</a>.<br/>W ich miejsce do zespołu <a href="https://autazeszwajcarii.pl">AutaZeSzwajcarii.pl</a> dołączyły nowe osoby.<br/><br/>Decyzje o zmianie organizacyjnej i zmianach w składzie osobowym podyktowane są koniecznością ochrony Państwa i moich interesów.<br/><br/>Przy tej okazji chciałbym stanowczo zaprzeczyć przekazywanym Państwu informacjom - oświadczam, że <a href="https://autazeszwajcarii.pl">AutaZeSzwajcarii.pl</a> jest portalem, którego byłem i jestem jedynym właścicielem. Nie planuję sprzedaży portalu, firmy, ograniczenia jej działalności czy dzielenia podmiotu - niezmiennie pozostaję wyłącznym właścicielem firmy i portalu aukcyjnego.<br/><br/><br/>Aktualne informacje o firmie i jej właścicielu oraz numerach telefonów oraz adresach e-mail znajdziecie Państwo na naszej stronie internetowej <a href="https://autazeszwajcarii.pl/kontakt">autazeszwajcarii.pl/kontakt</a> i stronie w portalu <a href="https://facebook.com/Autazeszwajcarii">facebook.com</a>.<br/><br/><br/>Zespół <a href="https://autazeszwajcarii.pl">AutaZeSzwajcarii.pl</a>, w nowym składzie, jest do Waszej dyspozycji pod numerem infolinii i niezmiennie numerem właściciela.<br/><br/>Nasze aktualne numery telefonów i adresy e-mail:<br/><br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>500 224 555</b>, biuro@autazeszwajcarii.pl biuro/infolinia<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>607 20 70 90</b>, dobre@autazeszwajcarii.pl Radek (właściciel)<br/><br/><br/>Dziękuję za uwagę. Pozdrawiam serdecznie i zapraszam do współpracy,<br/><br/>Radosław Galas<br/>właściciel<br/><a href="https://autazeszwajcarii.pl">autazeszwajcarii.pl</a><br/><br/>Podmiot odpowiedzialny:<br/>GALERIA OTWOCK GRAFFITI RADOSŁAW GALAS<br/>05-400 Otwock ul. Świderska 13'
#        message += '%s <br/><br/>' % (language_manager.get_trans(user.user, 'email-8'))

#        message += '<br/><br/>%s<br/>' % (language_manager.get_trans(user.user, 'email-9'))
#        message += language_manager.get_trans(user.user, 'email-10')
#        message += '<br/><br/>%s<br/>%s' % (language_manager.get_trans(user.user, 'email-11'), language_manager.get_trans(user.user, 'email-12'))

        print(user_email + ' ' + subject + ' ' + message)

        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_NORESPONSE,
                [user_email],
                html_message=htmlmessage,
                fail_silently=False,
            )
            logger.info('Sent email from %s to %s, subject: %s' % (settings.EMAIL_NORESPONSE, user_email, subject))
        except Exception as e:
            log_exception(e)
