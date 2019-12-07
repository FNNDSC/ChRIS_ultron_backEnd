# -*- coding: utf-8 -*-
"""
Local settings

- Run in Debug mode
- Use console backend for emails
- Add Django Debug Toolbar
- Add django-extensions as app
"""

from .common import *  # noqa
import os
import logging
import swiftclient


# avoid cluttered console output (for instance logging all the http requests)
logging.disable(logging.DEBUG)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'w1kxu^l=@pnsf!5piqz6!!5kdcdpo79y6jebbp+2244yjm*#+k'

# Hosts/domain names that are valid for this site
# See https://docs.djangoproject.com/en/1.6/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['*']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# pfcon service settings
PFCON = {
    'host': 'pfcon_service',
    'port': '5005'
}

# swift service settings
DEFAULT_FILE_STORAGE = 'swift.storage.SwiftStorage'
SWIFT_AUTH_URL = 'http://swift_service:8080/auth/v1.0'
SWIFT_USERNAME = 'chris:chris1234'
SWIFT_KEY = 'testing'
SWIFT_CONTAINER_NAME = 'users'
#SWIFT_AUTO_CREATE_CONTAINER = True
# initiate a swift service connection and create 'users' container
conn = swiftclient.Connection(
    user=SWIFT_USERNAME,
    key=SWIFT_KEY,
    authurl=SWIFT_AUTH_URL,
)
conn.put_container(SWIFT_CONTAINER_NAME)

# debug control output
CHRIS_DEBUG = {'quiet': True, 'debugFile': '/dev/null', 'useDebug': False}

if 'CHRIS_DEBUG_QUIET' in os.environ:
    CHRIS_DEBUG['quiet'] = bool(int(os.environ['CHRIS_DEBUG_QUIET']))

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases
DATABASES['default']['NAME'] = 'chris_dev'
DATABASES['default']['USER'] = 'chris'
DATABASES['default']['PASSWORD'] = 'Chris1234'
DATABASES['default']['TEST'] = {'CHARSET': 'utf8'}
DATABASES['default']['HOST'] = 'chris_dev_db'
DATABASES['default']['PORT'] = '3306'

# Mail settings
# ------------------------------------------------------------------------------
EMAIL_HOST = 'localhost'
EMAIL_PORT = 1025
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# django-debug-toolbar
# ------------------------------------------------------------------------------
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INSTALLED_APPS += ['debug_toolbar']

INTERNAL_IPS = ['127.0.0.1',]

DEBUG_TOOLBAR_CONFIG = {
    'DISABLE_PANELS': [
        'debug_toolbar.panels.redirects.RedirectsPanel',
    ],
    'SHOW_TEMPLATE_CONTEXT': True,
}

# django-extensions
# ------------------------------------------------------------------------------
INSTALLED_APPS += ['django_extensions']

# TESTING
# ------------------------------------------------------------------------------
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# corsheaders
# ------------------------------------------------------------------------------
CORS_ORIGIN_ALLOW_ALL = True
CORS_EXPOSE_HEADERS = ['Allow', 'Content-Type', 'Content-Length']
