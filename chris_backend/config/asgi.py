"""
ASGI config for chris_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

from django.core.asgi import get_asgi_application
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

application = get_asgi_application()
