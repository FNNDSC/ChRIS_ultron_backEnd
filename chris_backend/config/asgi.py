"""
ASGI config for chris_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# get_asgi_application MUST be called before other imports.
# https://github.com/django/channels/issues/1564#issuecomment-722354397
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from core.websockets.urls import websocket_urlpatterns
from core.websockets.auth import TokenQsAuthMiddleware

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')


# see https://channels.readthedocs.io/en/3.x/installation.html
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        TokenQsAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})
