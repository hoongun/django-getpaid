# -*- coding: utf-8 -*-
from django import forms


ADDITION_FIELDS = [
    'MNT_CUSTOM1',
    'MNT_CUSTOM2',
    'MNT_CUSTOM3',
    #'MNT_SUCCESS_URL',
    #'MNT_FAIL_URL',
    'moneta.locale',
    'paymentSystem.unitId',
    'paymentSystem.limitIds',
]


class PayForm(forms.Form):
    MNT_ID = forms.CharField(widget=forms.HiddenInput)
    MNT_CURRENCY_CODE = forms.CharField(widget=forms.HiddenInput)
    MNT_TEST_MODE = forms.CharField(widget=forms.HiddenInput)
    MNT_TRANSACTION_ID = forms.CharField(widget=forms.HiddenInput)
    MNT_AMOUNT = forms.CharField(required=False, widget=forms.HiddenInput)
    MNT_DESCRIPTION = forms.CharField(required=False, widget=forms.HiddenInput)
    MNT_SIGNATURE = forms.CharField(widget=forms.HiddenInput)

    # Form and field validation
    # https://docs.djangoproject.com/en/dev/ref/forms/validation/#ref-forms-validation

    def __init__(self, data, *args, **kwargs):
        addition_data = dict([(k, data.pop(k, None)) for k, v in data.items() if k in ADDITION_FIELDS])
        super(PayForm, self).__init__(data, *args, **kwargs)

        for k, v in addition_data.items():
            if v is not None:
                self.fields[k] = forms.CharField(widget=forms.HiddenInput(), initial=v)
