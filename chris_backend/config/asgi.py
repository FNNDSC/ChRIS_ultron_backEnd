"""
ASGI config for chris_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.websockets.urls import websocket_urlpatterns
from core.websockets.auth import TokenQsAuthMiddleware

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.security.websocket import AllowedHostsOriginValidator


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

django_asgi_app = get_asgi_application()

# see https://channels.readthedocs.io/en/3.x/installation.html
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        TokenQsAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})
