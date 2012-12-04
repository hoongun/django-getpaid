# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
import hashlib
import logging
from random import randint as rnd
import urllib
import urllib2

from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse, resolve
from django.db.models.loading import get_model
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from getpaid import signals
from getpaid.backends import PaymentProcessorBase

from xml_parsing import XMLParser


logger = logging.getLogger('getpaid.backends.platron')


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.platron'
    BACKEND_NAME = _('Platron')
    BACKEND_ACCEPTED_CURRENCY = ('RUR', )

    _INIT_PAYMENT_URL = 'https://www.platron.ru/init_payment.php'

    @staticmethod
    def _get_order(dic):
        flat = {}

        order = dic.keys()
        order.sort()

        for k, v in dic.items():
            if isinstance(dic[k], dict):
                deep_flat, deep_order = PaymentProcessor._get_order(v)
                flat.update(deep_flat)

                i = order.index(k)
                del order[i]
                order = order[:i] + deep_order + order[i:]
            else:
                flat[k] = v
        return flat, order

    @staticmethod
    def compute_sig(script_name, pg, secret_key):
        logger.debug('To compute: %s', pg)
        sig = ''
        flat_pg, order = PaymentProcessor._get_order(pg)
        for key in order:
            sig += flat_pg[key] + ';'
        logger.debug('SIGNATURE: %s', script_name + ';' + sig + secret_key)
        return hashlib.md5(script_name + ';' + sig + secret_key).hexdigest()

    @staticmethod
    def generate_salt():
        return hashlib.md5(str(rnd(99, 999999))).hexdigest()

    @staticmethod
    def send_response(script_name, description='', status='error'):
        key = PaymentProcessor.get_backend_setting('key')
        response = {
            'pg_salt': PaymentProcessor.generate_salt(),
            'pg_status': 'ok' if not description else status,
            'pg_description': description,
            'pg_error_description': description}
        response['pg_sig'] = PaymentProcessor.compute_sig(script_name, response, key)
        return XMLParser.to_xml(response, 'response')

    @staticmethod
    def online(xml, script_name):
        key = PaymentProcessor.get_backend_setting('key')
        currency = PaymentProcessor.get_backend_setting('currency')
        pg = XMLParser.to_dict(xml)

        # check signature
        if 'pg_sig' not in pg:
            return 'SIG ERR'
        else:
            sig = pg['pg_sig']
            del pg['pg_sig']
            if sig != PaymentProcessor.compute_sig(script_name, pg, key):
                return 'SIG ERR'

        # check currency
        if currency != pg['pg_ps_currency']:
            return 'CUR ERR'

        Payment = get_model('getpaid', 'Payment')
        try:
            payment = Payment.objects.select_related('order').get(pk=int(pg['pg_order_id']))
        except (Payment.DoesNotExist, ValueError):
            logger.error('Got message with CRC set to non existing Payment, %s' % str(pg))
            return 'CRC ERR'

        if pg.get('pg_can_rejected', None) == '1':
            return 'REJECT'

        result = pg.get('pg_result', None)
        if result == '1':
            payment.amount_paid = Decimal(pg['pg_amount'])
            payment.paid_on = datetime.utcnow().replace(tzinfo=utc)
            if payment.amount <= Decimal(pg['pg_amount']):
                payment.change_status('paid')
            else:
                payment.change_status('partially_paid')
        elif result == '0':
            description = pg.get('pg_description', None)
            logger.info('Non result response: %s', description)
            if payment.status != 'paid':
                payment.change_status('failed')
        else:
            # Check
            pass
        return 'OK'

    def get_gateway_url(self, request, payment_system_name=''):
        id = PaymentProcessor.get_backend_setting('id')
        key = PaymentProcessor.get_backend_setting('key')
        currency = PaymentProcessor.get_backend_setting('currency')
        testing = PaymentProcessor.get_backend_setting('testing')

        pg = {'pg_merchant_id': id,
              'pg_order_id': str(self.payment.pk),
              'pg_amount': str(self.payment.amount),
              'pg_currency': currency,

              # Getting from platron settings
              #'pg_check_url': '',
              #'pg_result_url': '',
              #'pg_refund_url': '',
              #'pg_request_method': '',
              #'pg_success_url': '',
              #'pg_failure_url': '',
              #'pg_success_url_method': '',
              #'pg_failure_url_method': '',

              'pg_payment_system': 'TEST' if bool(testing) else payment_system_name,

              # One day by default
              #'pg_lifetime': '',

              # UTF8 by default
              #'pg_encoding': '',


              'pg_description': 'TEST',

              # If not set - it will be asked on platron site
              #'pg_user_phone': '',
              #'pg_user_contact_email': '',
              #'pg_user_email': '',
              #'pg_user_cardholder': '',
              'pg_user_ip': request.META['REMOTE_ADDR'],

              #'pg_postpone_payment': '',

              # 'ru' by default
              #'pg_language': '',
              'pg_salt': str(PaymentProcessor.generate_salt())
        }

        user_data = {
              'email': '',
              'phone': '',
        }
        signals.user_data_query.send(sender=None, order=self.payment.order, user_data=user_data)
        if user_data['email']:
            pg['pg_user_email'] = user_data['email']
        if user_data['phone']:
            pg['pg_user_phone'] = user_data['phone']

        pg['pg_sig'] = PaymentProcessor.compute_sig('init_payment.php', pg, key)

        # Assembling XML-request
        xml_req = XMLParser.to_xml(pg)

        # Send payment request
        req = urllib2.Request(PaymentProcessor._INIT_PAYMENT_URL, data=xml_req)
        req.add_header('Content-Type', 'text/xml')
        xml_resp = urllib2.urlopen(req).read()

        # Parsing answer
        xml_dict = XMLParser.to_dict(xml_resp)

        gateway_url, params = '', {}
        if xml_dict['pg_status'] == 'error':
            logging.error('Payment request failed: %s', xml_req)
            params = {'pg_error_code': xml_dict['pg_error_code'],
                      'pg_error_description': xml_dict['pg_error_description'],
                      'pg_order_id': self.payment.pk}
            gateway_url = reverse('getpaid:platron:failure')
        else:
            gateway_url = xml_dict['pg_redirect_url']

        if PaymentProcessor.get_backend_setting('method', 'get').lower() == 'get':
            for key in params.keys():
                params[key] = unicode(params[key]).encode('utf-8')
            return gateway_url + '?' + urllib.urlencode(params), 'GET', {}
        else:
            raise ImproperlyConfigured('Platron payment backend accepts only GET')
