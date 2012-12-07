# -*- coding: utf-8 -*-
import logging

from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from getpaid.backends.payanyway import PaymentProcessor
from getpaid.models import Payment

logger = logging.getLogger('getpaid.backends.payanyway')


class OnlineView(View):
    def post(self, request, *args, **kwargs):
        try:
            command = request.POST.get('MNT_COMMAND', '')

            id = request.POST['MNT_ID']
            transaction_id = request.POST['MNT_TRANSACTION_ID']
            currency_code = request.POST['MNT_CURRENCY_CODE']
            test_mode = request.POST['MNT_TEST_MODE']
            signature = request.POST['MNT_SIGNATURE']

            if command:
                operation_id = request.POST.get('MNT_OPERATION_ID', '')
                amount = request.POST.get('MNT_AMOUNT', '')
            else:
                operation_id = request.POST['MNT_OPERATION_ID']
                amount = request.POST['MNT_AMOUNT']

            user = request.POST.get('MNT_USER', '')
            payment_system = request.POST.get('paymentSystem.unitId', '')
            corraccount = request.POST.get('MNT_CORRACCOUNT', '')
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('FAIL')

        status = PaymentProcessor.online(command=command, id=id, transaction_id=transaction_id,
                                         operation_id=operation_id, amount=amount,
                                         currency_code=currency_code, test_mode=test_mode, signature=signature,
                                         user=user, payment_system=payment_system, corraccount=corraccount)
        return HttpResponse(status)


class SuccessView(DetailView):
    """
    This view just redirects to standard backend success link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        return HttpResponseRedirect(reverse('getpaid:success-fallback', kwargs={'pk': self.object.pk}))


class FailureView(DetailView):
    """
    This view just redirects to standard backend failure link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        return HttpResponseRedirect(reverse('getpaid:failure-fallback', kwargs={'pk': self.object.pk}))
