from django.conf.urls.defaults import patterns, url
from django.views.decorators.csrf import csrf_exempt

from views import CheckView
from views import ResultView
from views import SuccessView
from views import FailureView

urlpatterns = patterns('',
    url(r'^check/?$', csrf_exempt(CheckView.as_view()), name='getpaid-platron-check'),
    url(r'^result/?$', csrf_exempt(ResultView.as_view()), name='getpaid-platron-result'),
    url(r'^success/$', csrf_exempt(SuccessView.as_view()), name='getpaid-platron-success'),
    url(r'^failure/$', csrf_exempt(FailureView.as_view()), name='getpaid-platron-failure'),
)
