"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from decimal import Decimal
from django.core.urlresolvers import reverse
from django.db.models.loading import get_model
from django.test.client import RequestFactory

from django.test import TestCase
from django.test.client import Client
import mock
import getpaid.backends.payu
import getpaid.backends.transferuj

from getpaid_test_project.orders.models import Order


class OrderTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_successful_create_payment_dummy_eur(self):
        """
        Tests if payment is successfully created
        """
        order = Order(name='Test EUR order', total=100, currency='EUR')
        order.save()
        response = self.client.post(reverse('getpaid:new-payment', kwargs={'currency' : 'EUR'}),
                    {'order': order.pk,
                     'backend': 'getpaid.backends.dummy'}
        )
        self.assertEqual(response.status_code, 302)
        Payment = get_model('getpaid', 'Payment')
        payment = Payment.objects.get(order=order.pk)
        self.assertEqual(payment.backend, 'getpaid.backends.dummy')
        self.assertEqual(payment.amount, order.total)
        self.assertEqual(payment.currency, order.currency)
        self.assertEqual(payment.status, 'in_progress')
        self.assertEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, 0)

    def test_successful_create_payment_payu_pln(self):
        """
        Tests if payment is successfully created
        """
        order = Order(name='Test PLN order', total=100, currency='PLN')
        order.save()
        response = self.client.post(reverse('getpaid:new-payment', kwargs={'currency' : 'PLN'}),
                {'order': order.pk,
                 'backend': 'getpaid.backends.payu'}
        )
        self.assertEqual(response.status_code, 302)
        Payment = get_model('getpaid', 'Payment')
        payment = Payment.objects.get(order=order.pk)
        self.assertEqual(payment.backend, 'getpaid.backends.payu')
        self.assertEqual(payment.amount, order.total)
        self.assertEqual(payment.currency, order.currency)
        self.assertEqual(payment.status, 'in_progress')
        self.assertEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, 0)


    def test_failure_create_payment_eur(self):
        """
        Tests if payment fails when wrong currency for backend.
        PayU accepts only PLN currency payments.
        """
        order = Order(name='Test EUR order', total=100, currency='EUR')
        order.save()
        response = self.client.post(reverse('getpaid:new-payment', kwargs={'currency' : 'EUR'}),
                    {'order': order.pk,
                     'backend': 'getpaid.backends.payu'}
        )
        self.assertEqual(response.status_code, 404)


def fake_payment_get_response_success(request):
    class fake_response:
        def read(self):
            return """<?xml version="1.0" encoding="UTF-8"?>
    <response>
    <status>OK</status>
    <trans>
    <id>234748067</id>
    <pos_id>123456789</pos_id>
    <session_id>99:1342616247.41</session_id>
    <order_id>99</order_id>
    <amount>12345</amount>
    <status>99</status>
    <pay_type>t</pay_type>
    <pay_gw_name>pt</pay_gw_name>
    <desc>Test 2</desc>
    <desc2></desc2>
    <create>2012-07-18 14:57:28</create>
    <init></init>
    <sent></sent>
    <recv></recv>
    <cancel>2012-07-18 14:57:30</cancel>
    <auth_fraud>0</auth_fraud>
    <ts>1342616255805</ts>
    <sig>4d4df5557b89a4e2d8c48436b1dd3fef</sig>	</trans>
</response>"""
    return fake_response()


def fake_payment_get_response_failure(request):
    class fake_response:
        def read(self):
            return """<?xml version="1.0" encoding="UTF-8"?>
    <response>
    <status>OK</status>
    <trans>
    <id>234748067</id>
    <pos_id>123456789</pos_id>
    <session_id>98:1342616247.41</session_id>
    <order_id>98</order_id>
    <amount>12345</amount>
    <status>2</status>
    <pay_type>t</pay_type>
    <pay_gw_name>pt</pay_gw_name>
    <desc>Test 2</desc>
    <desc2></desc2>
    <create>2012-07-18 14:57:28</create>
    <init></init>
    <sent></sent>
    <recv></recv>
    <cancel>2012-07-18 14:57:30</cancel>
    <auth_fraud>0</auth_fraud>
    <ts>1342616255805</ts>
    <sig>ee77e9515599e3fd2b3721dff50111dd</sig>	</trans>
</response>"""
    return fake_response()

class PayUBackendTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_online_malformed(self):
        response = self.client.post(reverse('getpaid:payu:online'), {})
        self.assertEqual(response.content, 'MALFORMED')

    def test_online_sig_err(self):
        response = self.client.post(reverse('getpaid:payu:online'), {
            'pos_id' : 'wrong',
            'session_id': '10:11111',
            'ts' : '1111',
            'sig' : 'wrong sig',
        })
        self.assertEqual(response.content, 'SIG ERR')

    def test_online_wrong_pos_id_err(self):
        response = self.client.post(reverse('getpaid:payu:online'), {
            'pos_id' : '12345',
            'session_id': '10:11111',
            'ts' : '1111',
            'sig' : '0d6129738c0aee9d4eb56f2a1db75ab4',
            })
        self.assertEqual(response.content, 'POS_ID ERR')

    def test_online_wrong_session_id_err(self):
        response = self.client.post(reverse('getpaid:payu:online'), {
            'pos_id' : '123456789',
            'session_id': '111111',
            'ts' : '1111',
            'sig' : 'fcf3db081d5085b45fe86ed0c6a9aa5e',
            })
        self.assertEqual(response.content, 'SESSION_ID ERR')

    def test_online_ok(self):
        response = self.client.post(reverse('getpaid:payu:online'), {
            'pos_id' : '123456789',
            'session_id': '1:11111',
            'ts' : '1111',
            'sig' : '2a78322c06522613cbd7447983570188',
            })
        self.assertEqual(response.content, 'OK')

    @mock.patch("urllib2.urlopen", fake_payment_get_response_success)
    def test_payment_get_paid(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(pk=99, order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=99) # this line is because django bug https://code.djangoproject.com/ticket/5903
        processor = getpaid.backends.payu.PaymentProcessor(payment)
        processor.get_payment_status('99:1342616247.41')
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertNotEqual(payment.amount_paid, Decimal('0'))

    @mock.patch("urllib2.urlopen", fake_payment_get_response_failure)
    def test_payment_get_failed(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(pk=98, order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=98) # this line is because django bug https://code.djangoproject.com/ticket/5903
        processor = getpaid.backends.payu.PaymentProcessor(payment)
        processor.get_payment_status('98:1342616247.41')
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('0'))

class TransferujBackendTest(TestCase):


    def test_online_not_allowed_ip(self):
        self.assertEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None,  None, None, None, None, None, None, None, None, None, None))

        #Tests allowing IP given in settings
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj' : {'allowed_ip': ('1.1.1.1', '1.2.3.4'), 'key': ''},
            }):
            self.assertEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None,  None, None, None, None, None, None, None, None, None, None))
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('1.1.1.1', None,  None, None, None, None, None, None, None, None, None, None))
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('1.2.3.4', None,  None, None, None, None, None, None, None, None, None, None))


        #Tests allowing all IP
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj' : {'allowed_ip': [], 'key': ''},
            }):
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None,  None, None, None, None, None, None, None, None, None, None))
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('1.1.1.1', None,  None, None, None, None, None, None, None, None, None, None))
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('1.2.3.4', None,  None, None, None, None, None, None, None, None, None, None))

    def test_online_wrong_sig(self):
        self.assertEqual('SIG ERR', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1', '123.45', None, None, None, None, None, 'xxx'))
        self.assertNotEqual('SIG ERR', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1', '123.45', None, None, None, None, None, '21b028c2dbdcb9ca272d1cc67ed0574e'))

    def test_online_wrong_id(self):
        self.assertEqual('ID ERR', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1111', '1', '', '1', '123.45', None, None, None, None, None, '15bb75707d4374bc6e578c0cbf5a7fc7'))
        self.assertNotEqual('ID ERR', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1', '123.45', None, None, None, None, None, 'f5f8276fbaa98a6e05b1056ab7c3a589'))

    def test_online_crc_error(self):
        self.assertEqual('CRC ERR', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '99999', '123.45', None, None, None, None, None, 'f5f8276fbaa98a6e05b1056ab7c3a589'))
        self.assertEqual('CRC ERR', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', 'GRRGRRG', '123.45', None, None, None, None, None, '6a9e045010c27dfed24774b0afa37d0b'))


    def test_online_payment_ok(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', payment.pk, '123.45', '123.45', '', 'TRUE', 0, '', '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('123.45'))

    def test_online_payment_ok_over(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', payment.pk, '123.45', '223.45', '', 'TRUE', 0, '', '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('223.45'))

    def test_online_payment_partial(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', payment.pk, '123.45', '23.45', '', 'TRUE', 0, '', '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'partially_paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('23.45'))

    def test_online_payment_failure(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', payment.pk, '123.45', '23.45', '', False, 0, '', '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'failed')


def platron_fake_success_init_payment(request):
    class fake_response:
        def read(self):
            return """<?xml version="1.0" encoding="utf-8"?>
                        <response>
                            <pg_salt>ijoi894j4ik39lo9</pg_salt>
                            <pg_status>ok</pg_status>
                            <pg_payment_id>15826</pg_payment_id>
                            <pg_redirect_url>https://www.platron.ru/payment_params.php?customer=ccaa41a4f425d124a23c3a53a3140bdc15826</pg_redirect_url>
                            <pg_redirect_url_type>need data</pg_redirect_url_type>
                            <pg_sig>af8e41a4f425d124a23c3a53a3140bdc17ea0</pg_sig>
                        </response>"""
    return fake_response()


def platron_fake_fail_init_payment(request):
    class fake_response:
        def read(self):
            return """<?xml version="1.0" encoding="utf-8"?>
                        <response>
                            <pg_status>error</pg_status>
                            <pg_error_code>101</pg_error_code>
                            <pg_error_description>Empty merchant</pg_error_description>
                        </response>"""
    return fake_response()


class PlatronBackendTest(TestCase):
    xml_check = """<?xml version="1.0" encoding="utf-8"?>
                    <request>
                        <pg_salt>qwertyuiop</pg_salt>
                        <pg_order_id>%s</pg_order_id>
                        <pg_payment_id>567890</pg_payment_id>
                        <pg_payment_system>WEBMONEYR</pg_payment_system>
                        <pg_amount>100.00</pg_amount>
                        <pg_currency>RUR</pg_currency>
                        <pg_ps_currency>%s</pg_ps_currency>
                        <pg_ps_amount>100.00</pg_ps_amount>
                        <pg_ps_full_amount>100.00</pg_ps_full_amount>
                        <uservar1>121212</uservar1>
                        <pg_sig>%s</pg_sig>
                    </request>
                    """

    xml_result = """<?xml version="1.0" encoding="utf-8"?>
                    <request>
                        <pg_salt>8765</pg_salt>
                        <pg_order_id>%s</pg_order_id>
                        <pg_payment_id>765432</pg_payment_id>
                        <pg_payment_system>WEBMONEYR</pg_payment_system>
                        <pg_amount>100.00</pg_amount>
                        <pg_net_amount>95.00</pg_net_amount>
                        <pg_currency>RUR</pg_currency>
                        <pg_ps_currency>RUR</pg_ps_currency>
                        <pg_ps_amount>100.00</pg_ps_amount>
                        <pg_ps_full_amount>100.00</pg_ps_full_amount>
                        <pg_result>%s</pg_result>
                        <pg_can_reject>0</pg_can_reject>
                        <pg_payment_date>2008-12-30 23:59:30</pg_payment_date>
                        <pg_card_brand>CA</pg_card_brand>
                        <uservar1>45363456</uservar1>
                        <pg_sig>%s</pg_sig>
                    </request>
                    """

    def setUp(self):
        self.client = Client()

    @mock.patch("urllib2.urlopen", platron_fake_success_init_payment)
    def test_success_init_payment(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='RUB')
        order.save()
        payment = Payment(pk=99, order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.platron')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=99)
        processor = getpaid.backends.platron.PaymentProcessor(payment)

        fake_request = RequestFactory()
        ip = {'REMOTE_ADDR': '123.123.123.123'}
        setattr(fake_request, 'META', ip)
        url, method, params = processor.get_gateway_url(fake_request)

        self.assertEqual(url, 'https://www.platron.ru/payment_params.php?customer=ccaa41a4f425d124a23c3a53a3140bdc15826')

    @mock.patch("urllib2.urlopen", platron_fake_fail_init_payment)
    def test_fail_init_payment(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='RUB')
        order.save()
        payment = Payment(pk=99, order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.platron')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=99)
        processor = getpaid.backends.platron.PaymentProcessor(payment)

        fake_request = RequestFactory()
        ip = {'REMOTE_ADDR': '123.123.123.123'}
        setattr(fake_request, 'META', ip)
        setattr(fake_request, 'path', '/getpaid.backends.platron/failure/')
        url, method, params = processor.get_gateway_url(fake_request)

        self.assertEqual(url, '/getpaid.backends.platron/failure/?pg_error_code=101&pg_order_id=99&pg_error_description=Empty+merchant')

    def test_online_wrong_sig(self):
        self.assertEqual('SIG ERR', getpaid.backends.platron.PaymentProcessor.online(self.xml_check % ('1234', 'RUR', 'xxxx'), 'check'))
        self.assertNotEqual('SIG ERR', getpaid.backends.platron.PaymentProcessor.online(self.xml_check % ('1234', 'RUR', 'ed57bad3c1b30649033bb7b3e3d33b86'), 'check'))

    def test_online_wrong_currency(self):
        self.assertEqual('CUR ERR', getpaid.backends.platron.PaymentProcessor.online(self.xml_check % ('1234', 'EUR', '78ae32e1e005d37d56be3342a292050b'), 'check'))
        self.assertNotEqual('CUR ERR', getpaid.backends.platron.PaymentProcessor.online(self.xml_check % ('1234', 'RUR', 'ed57bad3c1b30649033bb7b3e3d33b86'), 'check'))

    def test_online_crc_error(self):
        # TODO
        self.assertEqual('CRC ERR', getpaid.backends.platron.PaymentProcessor.online(self.xml_check % ('1111', 'RUR', 'e2947c340f12b8878fd86decdf09df37'), 'check'))
        self.assertEqual('CRC ERR', getpaid.backends.platron.PaymentProcessor.online(self.xml_check % ('1234', 'RUR', 'ed57bad3c1b30649033bb7b3e3d33b86'), 'check'))

    def test_online_rejected(self):
        pass

    def test_online_malformed(self):
        response = self.client.post(reverse('getpaid:platron:check'), {})
        self.assertEqual(response.content, 'MALFORMED')

    def test_send_response(self):
        check_url = reverse('getpaid:platron:check')
        result_url = reverse('getpaid:platron:result')

        response = self.client.post(check_url, {'pg_xml': self.xml_check % ('1234', 'RUR', 'xxxx')})
        self.assertContains(response, '<pg_status>error</pg_status>')
        response = self.client.post(check_url, {'pg_xml': self.xml_check % ('1234', 'EUR', '78ae32e1e005d37d56be3342a292050b')})
        self.assertContains(response, '<pg_status>error</pg_status>')
        response = self.client.post(check_url, {'pg_xml': self.xml_check % ('1111', 'RUR', 'e2947c340f12b8878fd86decdf09df37')})
        self.assertContains(response, '<pg_status>error</pg_status>')
        #TODO: with payment
        #response = self.client.post(check_url, {'pg_xml': self.xml_check % ('1234', 'RUR', 'ed57bad3c1b30649033bb7b3e3d33b86')})
        #self.assertContains(response, '<pg_status>ok</pg_status>')

        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='100.00', currency='RUB')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.platron')
        payment.save(force_insert=True)
        response = self.client.post(result_url, {'pg_xml': self.xml_result % (payment.pk, '1', '9b1a28ddd3a7317c5916a0bf42b2756c')})
        self.assertContains(response, '<pg_status>ok</pg_status>')

    def test_online_payment_ok(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='100.00', currency='RUB')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.platron')
        payment.save(force_insert=True)
        self.assertEqual('OK', getpaid.backends.platron.PaymentProcessor.online(self.xml_result % (payment.pk, '1', 'e668147fe238a3053d7aa1328749d31d'), 'result.php'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('100.00'))

        # repeat
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual('OK', getpaid.backends.platron.PaymentProcessor.online(self.xml_result % (payment.pk, '1', 'e668147fe238a3053d7aa1328749d31d'), 'result.php'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('100.00'))

    def test_online_payment_failure(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='RUB')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.platron')
        payment.save(force_insert=True)
        self.assertEqual('OK', getpaid.backends.platron.PaymentProcessor.online(self.xml_result % (payment.pk, '0', '84c11ec90ac8a6f637e3adfa912bab60'), 'result.php'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'failed')

    def test_success_fallback(self):
        pass

    def test_failure_fallback(self):
        pass


class PayAnyWayBackendTest(TestCase):
    """
    def test_online_not_allowed_ip(self):
        self.assertEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None,  None, None, None, None, None, None, None, None, None, None))

        #Tests allowing IP given in settings
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj' : {'allowed_ip': ('1.1.1.1', '1.2.3.4'), 'key': ''},
            }):
            self.assertEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None,  None, None, None, None, None, None, None, None, None, None))
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('1.1.1.1', None,  None, None, None, None, None, None, None, None, None, None))
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('1.2.3.4', None,  None, None, None, None, None, None, None, None, None, None))


        #Tests allowing all IP
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj' : {'allowed_ip': [], 'key': ''},
            }):
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None,  None, None, None, None, None, None, None, None, None, None))
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('1.1.1.1', None,  None, None, None, None, None, None, None, None, None, None))
            self.assertNotEqual('IP ERR', getpaid.backends.transferuj.PaymentProcessor.online('1.2.3.4', None,  None, None, None, None, None, None, None, None, None, None))
    """

    def test_online_wrong_sig(self):
        params = {
            'command': 'CHECK',
            'id': '1234',
            'transaction_id': '1234',
            'operation_id': '5678',
            'amount': '123.00',
            'currency_code': 'RUB',
            'test_mode': '0',
            'signature': 'xxx',
        }
        self.assertEqual('FAIL SIG ERR', getpaid.backends.payanyway.PaymentProcessor.online(**params))
        params['signature'] = '102153d9e5b8e97e7f0d608448e3e18f'
        self.assertNotEqual('FAIL SIG ERR', getpaid.backends.payanyway.PaymentProcessor.online(**params))

    def test_online_wrong_id(self):
        params = {
            'command': 'CHECK',
            'id': 'xxx',
            'transaction_id': '1234',
            'operation_id': '5678',
            'amount': '123.00',
            'currency_code': 'RUB',
            'test_mode': '0',
            'signature': 'd906166977815cc1772aee0ce476afdc',
        }
        self.assertEqual('FAIL ID ERR', getpaid.backends.payanyway.PaymentProcessor.online(**params))
        params['id'] = '1234'
        params['signature'] = '102153d9e5b8e97e7f0d608448e3e18f'
        self.assertNotEqual('FAIL ID ERR', getpaid.backends.payanyway.PaymentProcessor.online(**params))

    def test_online_crc_error(self):
        params = {
            'command': 'CHECK',
            'id': '1234',
            'transaction_id': 'xxx',
            'operation_id': '5678',
            'amount': '123.00',
            'currency_code': 'RUB',
            'test_mode': '0',
            'signature': '2c7ead8d6aef684842edb2806b4cb178',
        }
        self.assertEqual('FAIL CRC ERR', getpaid.backends.payanyway.PaymentProcessor.online(**params))

        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test transaction_id', total='123.00', currency='RUB')
        order.save()
        payment = Payment(pk=1234, order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payanyway')
        payment.save(force_insert=True)
        params['transaction_id'] = '1234'
        params['signature'] = '102153d9e5b8e97e7f0d608448e3e18f'
        self.assertNotEqual('FAIL CRC ERR', getpaid.backends.payanyway.PaymentProcessor.online(**params))

    #def test_check_request

    def test_online_payment_ok(self):
        params = {
            'command': '',
            'id': '1234',
            'transaction_id': '1234',
            'operation_id': '5678',
            'amount': '123.00',
            'currency_code': 'RUB',
            'test_mode': '0',
            'signature': 'dd0c3cb8216302bbd3a1aa21518667bc',
        }
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test pay', total='123.00', currency='RUB')
        order.save()
        payment = Payment(pk=1234, order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payanyway')
        payment.save(force_insert=True)
        self.assertEqual('SUCCESS', getpaid.backends.payanyway.PaymentProcessor.online(**params))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('123.00'))

    """
    def test_online_payment_ok_over(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', payment.pk, '123.45', '223.45', '', 'TRUE', 0, '', '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('223.45'))

    def test_online_payment_partial(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', payment.pk, '123.45', '23.45', '', 'TRUE', 0, '', '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'partially_paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('23.45'))

    def test_online_payment_failure(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', payment.pk, '123.45', '23.45', '', False, 0, '', '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'failed')
    """