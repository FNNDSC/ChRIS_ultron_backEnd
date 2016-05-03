# -*- coding: utf-8 -*-
"""
Local settings

- Run in Debug mode
- Use console backend for emails
- Add Django Debug Toolbar
- Add django-extensions as app
"""

from .common import *  # noqa

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'w1kxu^l=@pnsf!5piqz6!!5kdcdpo79y6jebbp+2244yjm*#+k'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases
DATABASES['default']['NAME'] = 'chris_dev'
DATABASES['default']['USER'] = 'chris'
DATABASES['default']['PASSWORD'] = 'Chris1234'

# Mail settings
# ------------------------------------------------------------------------------
EMAIL_HOST = 'localhost'
EMAIL_PORT = 1025
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# django-debug-toolbar
# ------------------------------------------------------------------------------
MIDDLEWARE_CLASSES += ['debug_toolbar.middleware.DebugToolbarMiddleware']
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

# Your local stuff: Below this line define 3rd party library settings
