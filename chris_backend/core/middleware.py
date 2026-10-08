
from functools import wraps

import django
from asgiref.sync import iscoroutinefunction, sync_to_async
from django.core.handlers import base as handlers_base
from django.core.handlers import exception as handlers_exception
from django.http import HttpResponse
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from django.conf import settings

from collectionjson.renderers import CollectionJsonRenderer


_django_convert_exception_to_response = handlers_exception.convert_exception_to_response


class RenderedResponse(HttpResponse):
    """
    An HttpResponse that renders its content into Collection+JSON or JSON.
    """

    def __init__(self, data, **kwargs):
        request = data.pop('request')
        mime = request.META.get('HTTP_ACCEPT')
        if mime == 'application/json':
            kwargs['content_type'] = 'application/json'
            data['error'] = data.pop('detail')
            renderer = JSONRenderer()
            content = renderer.render(data)
        else:
            kwargs['content_type'] = 'application/vnd.collection+json'
            self.exception = True
            renderer_context = {'request': request, 'view': None, 'response': self}
            renderer = CollectionJsonRenderer()
            content = renderer.render(data, renderer_context=renderer_context)
        super(RenderedResponse, self).__init__(content, **kwargs)


def api_500(request):
    return RenderedResponse({'detail': 'Internal server error', 'request': request},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResponseMiddleware(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception: Exception):
        if settings.DEBUG:
            raise exception
        print(exception, flush=True)
        mime = request.META.get('HTTP_ACCEPT')
        if mime != 'text/html':
            return api_500(request)


def convert_exception_to_response(get_response):
    """
    Django's ``convert_exception_to_response`` (which wraps every middleware) with the
    fix for Django ticket #36027 (commit 6fc8150, first in Django 6.2): in the async
    request path the error response is rendered on the request's thread-sensitive thread
    rather than on the event loop's default executor.

    Rendering an error response can query the database: the DEBUG 500 page prints the
    QuerySets in each stack frame, and without DEBUG the error email Django logs for the
    exception (when ``ADMINS`` is set) does the same and reports the request's user.
    A connection opened on an executor thread is never closed, because Django closes
    connections at the end of a request on the request's own thread, so each one is lost
    to the psycopg pool for the life of the process. Once a worker has lost all of them,
    every request that needs the database fails with ``PoolTimeout`` until a restart.

    This covers the exceptions that reach Django's error handling: every view exception
    under DEBUG (``ResponseMiddleware`` re-raises them) and, without DEBUG, the ones
    ``ResponseMiddleware`` does not answer (``text/html`` requests, middleware errors).
    It does not cover what Django logs for a response that is already a 500, such as
    ``api_500``, which Django still does on the executor; nor the static files handler,
    which upstream also changed and CUBE does not use.
    """
    if not iscoroutinefunction(get_response):
        return _django_convert_exception_to_response(get_response)

    @wraps(get_response)
    async def inner(request):
        try:
            response = await get_response(request)
        except Exception as exc:
            response = await sync_to_async(
                handlers_exception.response_for_exception, thread_sensitive=True
            )(request, exc)
        return response

    return inner


def backport_thread_sensitive_error_responses():
    """
    Install ``convert_exception_to_response`` above in place of Django's, which the
    handler applies to every middleware when it loads them. Must run before an ASGI
    handler is created, so it is called from ``Core.ready()``. A no-op from Django 6.2,
    which ships the fix; delete it then.
    """
    if django.VERSION >= (6, 2):
        return
    handlers_exception.convert_exception_to_response = convert_exception_to_response
    # the handler module imports the function by name
    handlers_base.convert_exception_to_response = convert_exception_to_response
