
from django.http import HttpResponse
from rest_framework import status
from rest_framework.renderers import JSONRenderer

from collectionjson.renderers import CollectionJsonRenderer


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

    def process_exception(self, request, exception):
        print(exception)
        mime = request.META.get('HTTP_ACCEPT')
        if mime != 'text/html':
            return api_500(request)
