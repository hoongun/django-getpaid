#noinspection PyUnresolvedReferences
from settings import *

GETPAID_BACKENDS = ('getpaid.backends.dummy',
                    'getpaid.backends.payanyway',
                    'getpaid.backends.payu',
                    'getpaid.backends.platron',
                    'getpaid.backends.transferuj',
                    )

INSTALLED_APPS += ('getpaid.backends.payanyway',
                   'getpaid.backends.payu',
                   'getpaid.backends.platron',
                   'getpaid.backends.transferuj',)

GETPAID_BACKENDS_SETTINGS = {
    # Please provide your settings for backends
    'getpaid.backends.payanyway': {
        'id': '1111',
        'key': 'ASDFG',
        'currency': 'RUB',
        'method': 'post',
        'testing': 'False',
        'demo': 'True',
        'demo_id': '1234',
        'demo_key': 'AAAAAAAA',
    },

    'getpaid.backends.payu': {
        'pos_id': 123456789,
        'key1': 'xxx',
        'key2': 'xxx',
        'pos_auth_key': 'xxx',
        'signing': True,
        #'testing': True,
    },

    'getpaid.backends.platron': {
        'id': '1234',
        'key': 'AAAAAAAA',
        'currency': 'RUB',
        'testing': 'True',
    },

    'getpaid.backends.transferuj': {
        'id': 1234,
        'key': 'AAAAAAAA',
    }
}
