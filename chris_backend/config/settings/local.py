# -*- coding: utf-8 -*-
"""
Local settings

- Run in Debug mode
- Use console backend for emails
- Add Django Debug Toolbar
- Add django-extensions as app
"""

import os
from .common import *  # noqa
from core.swiftmanager import SwiftManager

# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'w1kxu^l=@pnsf!5piqz6!!5kdcdpo79y6jebbp+2244yjm*#+k'

# Hosts/domain names that are valid for this site
# See https://docs.djangoproject.com/en/2.2/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['*']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# LOGGING CONFIGURATION
# See http://docs.djangoproject.com/en/2.2/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[%(asctime)s] [%(levelname)s]'
                      '[%(name)s][%(filename)s:%(lineno)d %(funcName)s] %(message)s'
        },
        'simple': {
            'format': '[%(asctime)s] [%(levelname)s]'
                      '[%(module)s %(process)d %(thread)d] %(message)s'
        },
    },
    'handlers': {
        'console_verbose': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'console_simple': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': '/tmp/debug.log',
            'formatter': 'simple'
        }
    },
    'loggers': {
        '': {  # root logger
            'level': 'INFO',
            'handlers': ['console_simple'],
        },
    }
}

for app in ['collectionjson', 'core', 'feeds', 'plugins', 'plugininstances', 'pipelines',
            'pipelineinstances', 'uploadedfiles', 'pacsfiles', 'servicefiles', 'users']:
    LOGGING['loggers'][app] = {
            'level': 'DEBUG',
            'handlers': ['console_verbose', 'file'],
            'propagate': False  # required to avoid double logging with root logger
        }

# Swift service settings
DEFAULT_FILE_STORAGE = 'swift.storage.SwiftStorage'
SWIFT_AUTH_URL = 'http://%s:8080/auth/v1.0' % os.getenv('SWIFT_HOSTNAME', 'swift_service')
SWIFT_USERNAME = 'chris:chris1234'
SWIFT_KEY = 'testing'
SWIFT_CONTAINER_NAME = 'users'
SWIFT_CONNECTION_PARAMS = {'user': SWIFT_USERNAME,
                           'key': SWIFT_KEY,
                           'authurl': SWIFT_AUTH_URL}
try:
    SwiftManager(SWIFT_CONTAINER_NAME, SWIFT_CONNECTION_PARAMS).create_container()
except Exception as e:
    raise ImproperlyConfigured(str(e))

# ChRIS store settings
CHRIS_STORE_URL = 'http://%s:8010/api/v1/' % os.getenv('STORE_HOSTNAME', 'chris-store.local')

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases
DATABASES['default']['NAME'] = 'chris_dev'
DATABASES['default']['USER'] = 'chris'
DATABASES['default']['PASSWORD'] = 'Chris1234'
DATABASES['default']['TEST'] = {'NAME': 'test_chris_dev'}
DATABASES['default']['HOST'] = os.getenv('DEV_DB_HOSTNAME', 'chris_dev_db')
DATABASES['default']['PORT'] = '5432'

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

COMPUTE_RESOURCE_URL = 'http://%s:30005/api/v1/' % os.getenv('PFCON_HOSTNAME', 'pfcon.remote')

# corsheaders
# ------------------------------------------------------------------------------
CORS_ORIGIN_ALLOW_ALL = True
CORS_EXPOSE_HEADERS = ['Allow', 'Content-Type', 'Content-Length']


# Celery settings

#CELERY_BROKER_URL = 'amqp://guest:guest@localhost'
CELERY_BROKER_URL = 'amqp://%s:5672' % os.getenv('QUEUE_HOSTNAME', 'queue')

#: Only add pickle to this list if your broker is secured
#: from unwanted access (see userguide/security.html)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Worker settings
# messages to prefetch at a time multiplied by the number of concurrent processes
# default is 4 (four messages for each process)
CELERYD_PREFETCH_MULTIPLIER = 2
