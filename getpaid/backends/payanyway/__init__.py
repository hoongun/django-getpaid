from datetime import datetime
from decimal import Decimal
import logging
import hashlib
import urllib

from django.core.exceptions import ImproperlyConfigured
from django.db.models.loading import get_model
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from getpaid import signals
from getpaid.backends import PaymentProcessorBase

import forms

logger = logging.getLogger('getpaid.backends.payanyway')


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.payanyway'
    BACKEND_NAME = _('PayAnyWay')
    BACKEND_ACCEPTED_CURRENCY = ('RUB',)

    _GATEWAY_URL = 'https://www.payanyway.ru/assistant.htm'
    _GATEWAY_URL_FOR_TEST = 'https://demo.moneta.ru/assistant.htm'

    _PAY_FORM_SIG_FIELDS = ('MNT_ID', 'MNT_TRANSACTION_ID', 'MNT_AMOUNT', 'MNT_CURRENCY_CODE', 'MNT_TEST_MODE')
    _PAY_SIG_FIELDS = ('id', 'transaction_id', 'operation_id', 'amount', 'currency_code', 'test_mode')
    _CHECK_SIG_FIELDS = ('command', ) + _PAY_SIG_FIELDS
    _CHECK_ANSWER_SIG_FIELDS = ('result_code', 'id', 'transaction_id')

    @staticmethod
    def compute_sig(params, fields, key):
        text = ''
        for field in fields:
            text += unicode(params.get(field, '')).encode('utf-8')
        text += key
        return hashlib.md5(text).hexdigest()

    @staticmethod
    def check(self, payment, *args, **params):
        if not payment:
            params['result_code'] = 302
        elif not params['amount']:
            params['result_code'] = 100
            params['amount'] = '%.2f' % Decimal(payment.amount)
        elif payment.status == 'paid':
            params['result_code'] = 200
        #elif order.is_blocked():
        #    params['result_code'] = 500
        else:
            params['result_code'] = 402
        logger.debug('Result code: %s', params['result_code'])

        # Send answer
        key = PaymentProcessor.get_backend_setting('key')
        params['signature'] = PaymentProcessor.compute_sig(params, PaymentProcessor._CHECK_ANSWER_SIG_FIELDS, key)
        return \
        '''<?xml version="1.0" encoding="UTF-8"?>
            <MNT_RESPONSE>
                    <MNT_ID>%(id)s</MNT_ID>
                    <MNT_TRANSACTION_ID>%(transaction_id)s</MNT_TRANSACTION_ID>
                    <MNT_RESULT_CODE>%(result_code)s</MNT_RESULT_CODE>
                    <MNT_DESCRIPTION>%(description)s</MNT_DESCRIPTION>
                    <MNT_AMOUNT>%(amount)s</MNT_AMOUNT>
                    <MNT_SIGNATURE>%(signature)s</MNT_SIGNATURE>
                    <MNT_ATTRIBUTES>
                        <ATTRIBUTE>
                            <KEY></KEY>
                            <VALUE></VALUE>
                        </ATTRIBUTE>
                    </MNT_ATTRIBUTES>
            </MNT_RESPONSE>
        ''' % params

    @staticmethod
    def online(self, *args, **params):
        key = PaymentProcessor.get_backend_setting('key')
        if params['signature'] != PaymentProcessor.compute_sig(params, PaymentProcessor._CHECK_SIG_FIELDS, key):
            logger.warning('Got message with wrong sig, %s' % str(params))
            return 'FAIL'

        Payment = get_model('getpaid', 'Payment')
        try:
            payment = Payment.objects.get(pk=int(params['transaction_id']))
        except (Payment.DoesNotExist, ValueError):
            logger.error('Got message with CRC set to non existing Payment, %s' % str(params))
            return 'FAIL'

        if params['command'] == 'CHECK':
            return PaymentProcessor.check(payment, params)
        elif payment and params['amount']:
            payment.amount_paid = Decimal(params['amount'])
            payment.paid_on = datetime.utcnow().replace(tzinfo=utc)
            if payment.amount <= Decimal(params['amount']):
                # Amount is correct or it is overpaid
                payment.change_status('paid')
            else:
                payment.change_status('partially_paid')
            return 'SUCCESS'
        elif payment.status != 'paid':
            payment.change_status('failed')
        return 'FAIL'

    def get_gateway_url(self, request):
        id = PaymentProcessor.get_backend_setting('id')
        key = PaymentProcessor.get_backend_setting('key')
        currency = PaymentProcessor.get_backend_setting('currency')
        testing = PaymentProcessor.get_backend_setting('testing')

        gateway_url = self._GATEWAY_URL
        if testing:
            gateway_url = self._GATEWAY_URL_FOR_TEST
            id = PaymentProcessor.get_backend_setting('test_id')
            key = PaymentProcessor.get_backend_setting('test_key')

        user_data = {
            'lang': None,
        }
        signals.user_data_query.send(sender=None, order=self.payment.order, user_data=user_data)
        if user_data['lang']:
            user_data['moneta_locale'] = user_data['lang']
        del user_data['lang']
        addition_user_data = dict([(k, v) for k, v in user_data.items() if k in forms.ADDITION_FIELDS])

        params = {
            'MNT_ID': id,
            'MNT_TRANSACTION_ID': str(self.payment.pk),
            'MNT_AMOUNT': '%.2f' % self.payment.amount,
            'MNT_CURRENCY_CODE': currency,
            'MNT_TEST_MODE': '1' if testing else '0',
        }
        params.update(addition_user_data)
        params['MNT_SIGNATURE'] = self.compute_sig(params, PaymentProcessor._PAY_FORM_SIG_FIELDS, key)

        if PaymentProcessor.get_backend_setting('method', 'get').lower() == 'post':
            return gateway_url, 'POST', params
        elif PaymentProcessor.get_backend_setting('method', 'get').lower() == 'get':
            for key in params.keys():
                params[key] = unicode(params[key]).encode('utf-8')
            return gateway_url + '?' + urllib.urlencode(params), 'GET', {}
        else:
            raise ImproperlyConfigured('PayAnyWay payment backend accepts only GET or POST')

    def get_form(self, params):
        return forms.PayForm(params)
