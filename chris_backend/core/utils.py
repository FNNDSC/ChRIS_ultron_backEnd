
import os
import json
import logging
import threading
import time
import zlib, base64

from django.conf import settings
from django.db import connections
from django.utils.crypto import salted_hmac


logger = logging.getLogger(__name__)


def get_file_resource_link(file_serializer, obj):
    """
    Utility function to get the hyperlink to the actual file resource from a
    file serializer.
    """
    fields = file_serializer.fields.items()
    # get the current url
    url_field = [v for (k, v) in fields if k == 'url'][0]
    view = url_field.view_name
    request = file_serializer.context['request']
    format = file_serializer.context['format']
    url = url_field.get_url(obj, view, request, format)
    # return url = current url + file name
    return url + os.path.basename(obj.fname.name)


def json_zip2str(json_data):
    """
    Return a string of compressed JSON data, suitable for transmission
    back to a client.
    """
    return base64.b64encode(
        zlib.compress(
            json.dumps(json_data).encode('utf-8')
        )
    ).decode('ascii')


def filter_files_by_n_slashes(queryset, value):
    """
    Utility function to return the files that have the queried number of slashes in
    their fname property. If the queried number ends in 'u' or 'U' then only one
    file per each last "folder" in the path is returned (useful to efficiently get
    the list of immediate folders under the path).
    """
    value = value.lower()
    try:
        if value.endswith('u'):
            val = int(value[:-1])
        else:
            val = int(value)
    except Exception:
        return queryset
    lookup = r'^[^/]+'
    for i in range(val):
        lookup += '/[^/]+'
    lookup += '$'
    qs = queryset.filter(fname__regex=lookup)
    if value.endswith('u'):
        return unique_files_queryset_by_folder(qs)
    return qs


def unique_files_queryset_by_folder(queryset):
    """
    Utility function to return only one file per each last "folder" in the path
    (useful to efficiently get the list of immediate folders under the path).
    """
    ids = []
    hash_set = set()
    for f in queryset.all():
        path = f.fname.name
        last_slash_ix = path.rindex('/')
        path = path[:last_slash_ix]
        if path not in hash_set:
            ids.append(f.id)
            hash_set.add(path)
    return queryset.filter(pk__in=ids)


def download_token_signing_key() -> bytes:
    """
    Utility function to return the key used to sign file download tokens.

    ``SECRET_KEY`` is not used directly. RFC 7518 Section 3.2 requires an HMAC key at
    least as long as the hash output — 64 bytes for HS512 — and a Django secret key is
    50 characters by default, so PyJWT >= 2.11 raises ``InsecureKeyLengthWarning`` on
    every encode and decode. Deriving a key gets the right length whatever the
    deployment sets, without asking operators to lengthen or rotate theirs.

    The salt makes this key specific to download tokens, so a component that later
    derives its own key from ``SECRET_KEY`` cannot land on the same bytes by coincidence.
    ``salted_hmac`` is Django's own idiom for exactly this, and it accepts a ``str`` or
    ``bytes`` secret.
    """
    return salted_hmac('core.utils.download_token_signing_key', '',
                       secret=settings.SECRET_KEY, algorithm='sha512').digest()


def db_pool_stats(alias='default'):
    """
    Utility function to return the counters of this process's psycopg connection pool
    for a database alias, or None when the database is not pooled. Adds ``checked_out``,
    the connections handed out and not yet returned: once the pool has settled it is 0
    unless some code still holds a connection. Opens no database connection.
    """
    pool = getattr(connections[alias], 'pool', None)
    if pool is None:
        return None

    stats = pool.get_stats()
    # a pool counts its min_size connections as soon as it is created, before it opens
    # them on the first request
    stats['checked_out'] = (0 if pool.closed
                            else stats['pool_size'] - stats['pool_available'])
    return stats


def start_db_pool_stats_logger(interval, alias='default'):
    """
    Utility function to log ``db_pool_stats()`` of this process every ``interval`` seconds
    from a daemon thread, as one ``db_pool_stats {json}`` line each time, so that the pool
    of every API worker can be read from the service log. Returns an event that stops the
    thread when set, or None without starting anything when ``interval`` is not positive.
    """
    if interval <= 0:
        return None

    stop = threading.Event()

    def log_stats():
        while not stop.wait(interval):
            try:
                stats = db_pool_stats(alias)
            except Exception as e:
                logger.warning('could not read the %s connection pool: %s', alias, e)
                continue

            if stats is not None:
                logger.info('db_pool_stats %s', json.dumps(
                    {'pid': os.getpid(), 'ts': time.time(), 'alias': alias, **stats}))

    threading.Thread(target=log_stats, name='db-pool-stats', daemon=True).start()
    return stop
