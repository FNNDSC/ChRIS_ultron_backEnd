# -*- coding: utf-8 -*-
"""
Production Configurations

"""

import ldap
from django_auth_ldap.config import LDAPSearch
from .common import *  # noqa
from environs import Env, EnvValidationError
from core.storage import verify_storage_connection

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
# See: https://docs.djangoproject.com/en/4.2/ref/settings/#secret-key
# Raises ImproperlyConfigured exception if DJANGO_SECRET_KEY not in os.environ
SECRET_KEY = get_secret('DJANGO_SECRET_KEY')


# SITE CONFIGURATION
# ------------------------------------------------------------------------------
# Hosts/domain names that are valid for this site
# See https://docs.djangoproject.com/en/4.2/ref/settings/#allowed-hosts
ALLOWED_HOSTS = get_secret('DJANGO_ALLOWED_HOSTS', env.list)
# END SITE CONFIGURATION


# DATABASE CONFIGURATION
# ------------------------------------------------------------------------------
DATABASES['default']['NAME'] = get_secret('POSTGRES_DB')
DATABASES['default']['USER'] = get_secret('POSTGRES_USER')
DATABASES['default']['PASSWORD'] = get_secret('POSTGRES_PASSWORD')
DATABASES['default']['HOST'] = get_secret('DATABASE_HOST')
DATABASES['default']['PORT'] = get_secret('DATABASE_PORT')


# STORAGE CONFIGURATION
# ------------------------------------------------------------------------------
STORAGE_ENV = get_secret('STORAGE_ENV')
if STORAGE_ENV not in ('swift', 'filesystem'):
    raise ImproperlyConfigured(f"Unsupported value '{STORAGE_ENV}' for STORAGE_ENV")

if STORAGE_ENV == 'swift':
    STORAGES['default'] = {'BACKEND': 'swift.storage.SwiftStorage'}
    SWIFT_AUTH_URL = get_secret('SWIFT_AUTH_URL')
    SWIFT_USERNAME = get_secret('SWIFT_USERNAME')
    SWIFT_KEY = get_secret('SWIFT_KEY')
    SWIFT_CONTAINER_NAME = get_secret('SWIFT_CONTAINER_NAME')
    SWIFT_CONNECTION_PARAMS = {'user': SWIFT_USERNAME,
                               'key': SWIFT_KEY,
                               'authurl': SWIFT_AUTH_URL}
    verify_storage = lambda: verify_storage_connection(
        DEFAULT_FILE_STORAGE=STORAGES['default']['BACKEND'],
        SWIFT_CONTAINER_NAME=SWIFT_CONTAINER_NAME,
        SWIFT_CONNECTION_PARAMS=SWIFT_CONNECTION_PARAMS
    )
elif STORAGE_ENV == 'filesystem':
    STORAGES['default'] = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
    MEDIA_ROOT = get_secret('MEDIA_ROOT')
    verify_storage = lambda: verify_storage_connection(DEFAULT_FILE_STORAGE=STORAGES['default']['BACKEND'],
                                                       MEDIA_ROOT=MEDIA_ROOT)
else:
    verify_storage = lambda: verify_storage_connection()

try:
    verify_storage()
except Exception as e:
    raise ImproperlyConfigured(str(e))


# CHRIS STORE SERVICE CONFIGURATION
CHRIS_STORE_URL = get_secret('CHRIS_STORE_URL')


# LOGGING CONFIGURATION
# See https://docs.djangoproject.com/en/4.2/topics/logging/ for
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
            'formatter': 'console',
        },
    },
    'loggers': {
        '': {  # root logger
            'level': 'INFO',
            'handlers': ['console'],
        }
    }
}


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

    _user_search = env.str('AUTH_LDAP_USER_SEARCH_FILTER', default='(uid=%(user)s)')
    AUTH_LDAP_USER_SEARCH = LDAPSearch(AUTH_LDAP_USER_SEARCH_ROOT, ldap.SCOPE_SUBTREE,
                                       _user_search)
    AUTH_LDAP_USER_ATTR_MAP = env.dict(
        'AUTH_LDAP_USER_ATTR_MAP',
        default={
            'first_name': 'givenName',
            'last_name': 'sn',
            'email': 'mail'
        }
    )
    AUTHENTICATION_BACKENDS = (
        'django_auth_ldap.backend.LDAPBackend',
        'django.contrib.auth.backends.ModelBackend',
    )
