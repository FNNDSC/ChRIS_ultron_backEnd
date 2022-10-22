# -*- coding: utf-8 -*-
"""
Production Configurations

"""

import sys
import ldap
from django_auth_ldap.config import LDAPSearch
from .common import *  # noqa
from environs import Env, EnvValidationError
from core.swiftmanager import SwiftManager

# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured


# Environment variables-based secrets
env = Env()
env.read_env()  # also read .env file, if it exists


def get_secret(setting, secret_type=env):
    """Get the secret variable or return explicit exception."""
    try:
        return secret_type(setting)
    except EnvValidationError as e:
        raise ImproperlyConfigured(str(e))


# SECRET CONFIGURATION
# ------------------------------------------------------------------------------
# See: https://docs.djangoproject.com/en/4.0/ref/settings/#secret-key
# Raises ImproperlyConfigured exception if DJANGO_SECRET_KEY not in os.environ
SECRET_KEY = get_secret('DJANGO_SECRET_KEY')


# SITE CONFIGURATION
# ------------------------------------------------------------------------------
# Hosts/domain names that are valid for this site
# See https://docs.djangoproject.com/en/4.0/ref/settings/#allowed-hosts
ALLOWED_HOSTS = get_secret('DJANGO_ALLOWED_HOSTS', env.list)
# END SITE CONFIGURATION


# DATABASE CONFIGURATION
# ------------------------------------------------------------------------------
# Raises ImproperlyConfigured exception if DATABASE_URL not set
DATABASES['default']['NAME'] = get_secret('POSTGRES_DB')
DATABASES['default']['USER'] = get_secret('POSTGRES_USER')
DATABASES['default']['PASSWORD'] = get_secret('POSTGRES_PASSWORD')
DATABASES['default']['HOST'] = get_secret('DATABASE_HOST')
DATABASES['default']['PORT'] = get_secret('DATABASE_PORT')


# SWIFT SERVICE CONFIGURATION
# ------------------------------------------------------------------------------
DEFAULT_FILE_STORAGE = 'swift.storage.SwiftStorage'
SWIFT_AUTH_URL = get_secret('SWIFT_AUTH_URL')
SWIFT_USERNAME = get_secret('SWIFT_USERNAME')
SWIFT_KEY = get_secret('SWIFT_KEY')
SWIFT_CONTAINER_NAME = get_secret('SWIFT_CONTAINER_NAME')
SWIFT_CONNECTION_PARAMS = {'user': SWIFT_USERNAME,
                           'key': SWIFT_KEY,
                           'authurl': SWIFT_AUTH_URL}
try:
    SwiftManager(SWIFT_CONTAINER_NAME, SWIFT_CONNECTION_PARAMS).create_container()
except Exception as e:
    raise ImproperlyConfigured(str(e))


# CHRIS STORE SERVICE CONFIGURATION
CHRIS_STORE_URL = get_secret('CHRIS_STORE_URL')


# LOGGING CONFIGURATION
# See https://docs.djangoproject.com/en/4.0/topics/logging/ for
# more details on how to customize your logging configuration.
ADMINS = [('FNNDSC Developers', 'dev@babymri.org')]
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '[%(levelname)s][%(module)s %(process)d %(thread)d] %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'console',
        },
    },
    'loggers': {
        '': {  # root logger
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': True,
        }
    }
}


# STATIC FILES (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/
STATIC_ROOT = get_secret('STATIC_ROOT')


# CORSHEADERS
# ------------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = get_secret('DJANGO_CORS_ALLOW_ALL_ORIGINS', env.bool)
CORS_ALLOWED_ORIGINS = get_secret('DJANGO_CORS_ALLOWED_ORIGINS', env.list)


# CELERY SETTINGS
# ------------------------------------------------------------------------------
CELERY_BROKER_URL = get_secret('CELERY_BROKER_URL')

#: Only add pickle to this list if your broker is secured
#: from unwanted access (see userguide/security.html)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Worker settings
# messages to prefetch at a time multiplied by the number of concurrent processes
# default is 4 (four messages for each process)
CELERYD_PREFETCH_MULTIPLIER = 2


# REVERSE PROXY
# ------------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = get_secret('DJANGO_SECURE_PROXY_SSL_HEADER', env.list)
SECURE_PROXY_SSL_HEADER = tuple(SECURE_PROXY_SSL_HEADER) if SECURE_PROXY_SSL_HEADER else None
USE_X_FORWARDED_HOST = get_secret('DJANGO_USE_X_FORWARDED_HOST', env.bool)


# LDAP AUTH CONFIGURATION
# ------------------------------------------------------------------------------
AUTH_LDAP = get_secret('AUTH_LDAP', env.bool)
if AUTH_LDAP:
    AUTH_LDAP_SERVER_URI = get_secret('AUTH_LDAP_SERVER_URI')
    AUTH_LDAP_BIND_DN = get_secret('AUTH_LDAP_BIND_DN')
    AUTH_LDAP_BIND_PASSWORD = get_secret('AUTH_LDAP_BIND_PASSWORD')
    AUTH_LDAP_USER_SEARCH_ROOT = get_secret('AUTH_LDAP_USER_SEARCH_ROOT')

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
