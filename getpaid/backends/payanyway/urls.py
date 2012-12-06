from django.conf.urls.defaults import patterns, url
from django.views.decorators.csrf import csrf_exempt

from views import OnlineView
from views import SuccessView
from views import FailureView

urlpatterns = patterns('',
    url(r'^online/?$', csrf_exempt(OnlineView.as_view()), name='online'),
    url(r'^success/?$', csrf_exempt(SuccessView.as_view()), name='success'),
    url(r'^failure/?$', csrf_exempt(FailureView.as_view()), name='failure'),
)
