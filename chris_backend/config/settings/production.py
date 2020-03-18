# -*- coding: utf-8 -*-
"""
Production Configurations

"""

from .common import *  # noqa
# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured

from environs import Env, EnvValidationError
import swiftclient


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
# See: https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
# Raises ImproperlyConfigured exception if DJANGO_SECRET_KEY not in os.environ
SECRET_KEY = get_secret('DJANGO_SECRET_KEY')


# SITE CONFIGURATION
# ------------------------------------------------------------------------------
# Hosts/domain names that are valid for this site
# See https://docs.djangoproject.com/en/1.6/ref/settings/#allowed-hosts
ALLOWED_HOSTS = get_secret('DJANGO_ALLOWED_HOSTS', env.list)
# END SITE CONFIGURATION


# DATABASE CONFIGURATION
# ------------------------------------------------------------------------------
# Raises ImproperlyConfigured exception if DATABASE_URL not in os.environ
DATABASES['default']['NAME'] = get_secret('MYSQL_DATABASE')
DATABASES['default']['USER'] = get_secret('MYSQL_USER')
DATABASES['default']['PASSWORD'] = get_secret('MYSQL_PASSWORD')
DATABASES['default']['HOST'] = get_secret('DATABASE_HOST')
DATABASES['default']['PORT'] = get_secret('DATABASE_PORT')


# SWIFT SERVICE CONFIGURATION
# ------------------------------------------------------------------------------
DEFAULT_FILE_STORAGE = 'swift.storage.SwiftStorage'
SWIFT_AUTH_URL = get_secret('SWIFT_AUTH_URL')
SWIFT_USERNAME = get_secret('SWIFT_USERNAME')
SWIFT_KEY = get_secret('SWIFT_KEY')
SWIFT_CONTAINER_NAME = get_secret('SWIFT_CONTAINER_NAME')
SWIFT_AUTO_CREATE_CONTAINER = True
# initiate a swift service connection and create 'users' container
conn = swiftclient.Connection(
    user=SWIFT_USERNAME,
    key=SWIFT_KEY,
    authurl=SWIFT_AUTH_URL,
)
conn.put_container(SWIFT_CONTAINER_NAME)


# CHRIS STORE SERVICE CONFIGURATION
CHRIS_STORE_URL = get_secret('CHRIS_STORE_URL')


# PFCON SERVICE CONFIGURATION
# ------------------------------------------------------------------------------
PFCON = {
    'host': get_secret('PFCON_HOST'),
    'port': get_secret('PFCON_PORT')
}


# CHARM DEBUG CONTROL OUTPUT
CHRIS_DEBUG = {'quiet': True, 'debugFile': '/dev/null', 'useDebug': False}
CHRIS_DEBUG['quiet'] = get_secret('CHRIS_DEBUG_QUIET', env.bool)


# LOGGING CONFIGURATION
# ------------------------------------------------------------------------------
# See: https://docs.djangoproject.com/en/dev/ref/settings/#logging
# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s '
                      '%(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True
        },
        'django.security.DisallowedHost': {
            'level': 'ERROR',
            'handlers': ['console', 'mail_admins'],
            'propagate': True
        }
    }
}


# STATIC FILES (CSS, JavaScript, Images)
STATIC_ROOT = get_secret('STATIC_ROOT')


# Your production stuff: Below this line define 3rd party library settings

# corsheaders
# ------------------------------------------------------------------------------
CORS_ORIGIN_ALLOW_ALL = get_secret('DJANGO_CORS_ORIGIN_ALLOW_ALL', env.bool)
CORS_ORIGIN_WHITELIST = get_secret('DJANGO_CORS_ORIGIN_WHITELIST', env.list)


# Celery settings

#CELERY_BROKER_URL = 'amqp://guest:guest@localhost'
CELERY_BROKER_URL = get_secret('CELERY_BROKER_URL')

#: Only add pickle to this list if your broker is secured
#: from unwanted access (see userguide/security.html)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
