from django.core.urlresolvers import reverse, resolve
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from getpaid.backends.platron import PaymentProcessor
from getpaid.models import Payment


class OnlineView(View):
    script_name = ''

    def get_response(self, status):
        status_dict = {'SIG ERR': [u'Signature failure'],
                        'CUR ERR': [u'Bad currency'],
                        'CRC ERR': [u'Order id is not found'],
                        'REJECT': [u'Payment rejected', 'rejected'],
                        'OK': ['']}
        return PaymentProcessor.send_response(self.script_name, *status_dict.get(status, ['']))

    def post(self, request, *args, **kwargs):
        try:
            xml = request.POST['pg_xml']
        except KeyError:
            #logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('MALFORMED')

        status = PaymentProcessor.online(xml, self.script_name)
        return HttpResponse(self.get_response(status))


class CheckView(OnlineView):
    script_name = 'check'


class ResultView(OnlineView):
    script_name = 'result'


class SuccessView(View):
    """
    This view just redirects to standard backend success link.
    """

    def get(self, request, *args, **kwargs):
        pk = request.GET.get('pg_order_id', None)
        return HttpResponseRedirect(reverse('getpaid:success-fallback', kwargs={'pk': pk}))


class FailureView(View):
    """
    This view just redirects to standard backend failure link.
    """

    def get(self, request, *args, **kwargs):
        pk = request.GET.get('pg_order_id', None)
        return HttpResponseRedirect(reverse('getpaid:failure-fallback', kwargs={'pk': pk}))