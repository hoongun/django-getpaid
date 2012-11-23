# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
import hashlib
import logging
from random import randint as rnd
import urllib
import urllib2
from xml.etree.ElementTree import XMLParser

from django.core.urlresolvers import reverse, resolve
from django.db.models.loading import get_model
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from getpaid.backends import PaymentProcessorBase

from xml_parsing import RequestTemplate, ResponseTemplate

logger = logging.getLogger('getpaid.backends.platron')


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.platron'
    BACKEND_NAME = _('Platron')
    BACKEND_ACCEPTED_CURRENCY = ('RUR', )

    _INIT_PAYMENT_URL = 'https://www.platron.ru/init_payment.php'

    @staticmethod
    def compute_sig(script_name, pg, secret_key):
        logger.debug('To compute: %s', pg)
        sig, keys = '', pg.keys()
        keys.sort()
        for key in keys:
            sig += pg[key] + ';'
        logger.debug('SIGNATURE: %s', script_name + ';' + sig + secret_key)
        return hashlib.md5(script_name + ';' + sig + secret_key).hexdigest()

    @staticmethod
    def serialize(elements, type='request'):
        params = ''
        for key, value in elements.items():
            params += '  <%(key)s>%(value)s</%(key)s>\n' % {'key': key, 'value': value}

        xml = '<?xml version="1.0" encoding="utf-8"?>'\
                '<%(type)s>\n%(params)s</%(type)s>' % {'type': type, 'params': params}
        return xml

    @staticmethod
    def deserialize(xml):
        if xml.find('<response>') >= 0:
            target = ResponseTemplate()
        elif xml.find('<request>') >= 0:
            target = RequestTemplate()
        else:
            return {}
        parser = XMLParser(target=target)
        parser.feed(xml)
        return parser.close()

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
        return PaymentProcessor.serialize(response, 'response')

    @staticmethod
    def online(xml, script_name):
        key = PaymentProcessor.get_backend_setting('key')
        currency = PaymentProcessor.get_backend_setting('currency')
        pg = PaymentProcessor.deserialize(xml)

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
              'pg_salt': str(PaymentProcessor.generate_salt())}
        pg['pg_sig'] = PaymentProcessor.compute_sig('init_payment.php', pg, key)

        # Assembling XML-request
        xml_req = PaymentProcessor.serialize(pg)

        # Send payment request
        req = urllib2.Request(PaymentProcessor._INIT_PAYMENT_URL, data=xml_req)
        req.add_header('Content-Type', 'text/xml')
        xml_resp = urllib2.urlopen(req).read()

        # Parsing answer
        xml_dict = PaymentProcessor.deserialize(xml_resp)

        if xml_dict['pg_status'] == 'error':
            logging.error('Payment request failed: %s', xml_req)
            params = {'pg_error_code': unicode(xml_dict['pg_error_code']).encode('utf-8'),
                      'pg_error_description': unicode(xml_dict['pg_error_description']).encode('utf-8'),
                      'pg_order_id': self.payment.pk}
            ns = resolve(request.path).namespace
            ns = '%s:' % ns if ns else ''
            return reverse('%sgetpaid-platron-failure' % ns) + '?' + urllib.urlencode(params)
        return xml_dict['pg_redirect_url']
