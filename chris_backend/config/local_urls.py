from django.urls import path, include
from django.conf import settings

from .urls import urlpatterns as production_urlpatterns

urlpatterns = production_urlpatterns

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
