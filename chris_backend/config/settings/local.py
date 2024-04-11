# -*- coding: utf-8 -*-
"""
Local settings

- Run in Debug mode
- Use console backend for emails
- Add Django Debug Toolbar
- Add django-extensions as app
"""

import os
import ldap
from django_auth_ldap.config import LDAPSearch
from .common import *  # noqa
from core.storage import verify_storage_connection

# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'w1kxu^l=@pnsf!5piqz6!!5kdcdpo79y6jebbp+2244yjm*#+k'

# Hosts/domain names that are valid for this site
# See https://docs.djangoproject.com/en/4.2/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['*']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# LOGGING CONFIGURATION
# See https://docs.djangoproject.com/en/4.2/topics/logging/ for
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

for app in ['collectionjson', 'core', 'feeds', 'plugins', 'plugininstances',
            'pipelines', 'userfiles', 'pacsfiles', 'users', 'filebrowser',
            'workflows']:
    LOGGING['loggers'][app] = {
            'level': 'DEBUG',
            'handlers': ['console_verbose', 'file'],
            'propagate': False  # required to avoid double logging with root logger
        }

# Storage Settings
STORAGE_ENV = os.getenv('STORAGE_ENV', 'swift')
if STORAGE_ENV not in ('swift', 'fslink', 'filesystem'):
    raise ImproperlyConfigured(f"Unsupported value '{STORAGE_ENV}' for STORAGE_ENV")

STORAGES['default'] = {'BACKEND': 'swift.storage.SwiftStorage'}
SWIFT_AUTH_URL = 'http://swift_service:8080/auth/v1.0'  # Swift service settings
SWIFT_USERNAME = 'chris:chris1234'
SWIFT_KEY = 'testing'
SWIFT_CONTAINER_NAME = 'users'
SWIFT_CONNECTION_PARAMS = {'user': SWIFT_USERNAME,
                           'key': SWIFT_KEY,
                           'authurl': SWIFT_AUTH_URL}
MEDIA_ROOT = None
if STORAGE_ENV in ('fslink', 'filesystem'):
    STORAGES['default'] = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
    MEDIA_ROOT = '/var/chris'  # local filesystem storage settings

try:
    verify_storage_connection(
        DEFAULT_FILE_STORAGE=STORAGES['default']['BACKEND'],
        MEDIA_ROOT=MEDIA_ROOT,
        SWIFT_CONTAINER_NAME=SWIFT_CONTAINER_NAME,
        SWIFT_CONNECTION_PARAMS=SWIFT_CONNECTION_PARAMS
    )
except Exception as e:
    raise ImproperlyConfigured(str(e))

# ChRIS store settings
CHRIS_STORE_URL = 'http://chris-store.local:8010/api/v1/'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES['default']['NAME'] = 'chris_dev'
DATABASES['default']['USER'] = 'chris'
DATABASES['default']['PASSWORD'] = 'Chris1234'
DATABASES['default']['TEST'] = {'NAME': 'test_chris_dev'}
DATABASES['default']['HOST'] = 'chris_dev_db'
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

COMPUTE_RESOURCE_URL = 'http://pfcon.remote:30005/api/v1/'

# corsheaders
# ------------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True
CORS_EXPOSE_HEADERS = ['Allow', 'Content-Type', 'Content-Length']


# Celery settings

#CELERY_BROKER_URL = 'amqp://guest:guest@localhost'
CELERY_BROKER_URL = 'amqp://queue:5672'

#: Only add pickle to this list if your broker is secured
#: from unwanted access (see userguide/security.html)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Worker settings
# messages to prefetch at a time multiplied by the number of concurrent processes
# default is 4 (four messages for each process)
CELERYD_PREFETCH_MULTIPLIER = 2


# LDAP auth configuration
AUTH_LDAP = True
if AUTH_LDAP:
    AUTH_LDAP_SERVER_URI = 'ldap://lldap:3890'
    AUTH_LDAP_BIND_DN = 'uid=admin,ou=people,dc=example,dc=org'
    AUTH_LDAP_BIND_PASSWORD = 'chris1234'
    AUTH_LDAP_USER_SEARCH_ROOT = 'ou=people,dc=example,dc=org'

    AUTH_LDAP_USER_SEARCH = LDAPSearch(AUTH_LDAP_USER_SEARCH_ROOT, ldap.SCOPE_SUBTREE,
                                       '(uid=%(user)s)')
    AUTH_LDAP_USER_ATTR_MAP = {
        'first_name': 'givenName',
        'last_name': 'sn',
        'email': 'mail'
    }
    AUTHENTICATION_BACKENDS = (
        'django_auth_ldap.backend.LDAPBackend',
        'django.contrib.auth.backends.ModelBackend',
    )
