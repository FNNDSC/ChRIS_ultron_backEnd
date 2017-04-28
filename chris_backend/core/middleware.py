
from django.http import HttpResponse

from rest_framework import status
from rest_framework.renderers import JSONRenderer

from collectionjson.renderers import CollectionJsonRenderer


class RenderedResponse(HttpResponse):
    """
    An HttpResponse that renders its content into Collection+JSON or JSON.
    """
    def __init__(self, data, **kwargs):
        kwargs['status'] = data['status']
        del data['status']
        request = data['request']
        del data['request']
        mime = request.META.get('HTTP_ACCEPT')
        if mime=='application/json':
            kwargs['content_type'] = 'application/json'
            data['error'] = data['detail']
            del data['detail']
            content = JSONRenderer().render(data)
        else:
            kwargs['content_type'] = 'application/vnd.collection+json'
            self.exception = True
            renderer_context = {}
            renderer_context['request'] = request
            renderer_context['view'] = None
            renderer_context['response'] = self
            content = CollectionJsonRenderer().render(data,
                                                      renderer_context=renderer_context)
        super(RenderedResponse, self).__init__(content, **kwargs)


def api_301(request):
    return RenderedResponse({'detail': 'Moved Permanently', 'request':request,
                       'status': status.HTTP_301_MOVED_PERMANENTLY})

def api_404(request):
    return RenderedResponse({'detail': 'Not found', 'request':request,
                       'status': status.HTTP_404_NOT_FOUND})

def api_500(request):
    return RenderedResponse({'detail': 'Internal server error', 'request':request,
                       'status': status.HTTP_500_INTERNAL_SERVER_ERROR})


class ResponseMiddleware(object):

    def process_response(self, request, response):
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return api_404(request)
        if response.status_code == status.HTTP_301_MOVED_PERMANENTLY:
            return api_301(request)
        return response

    def process_exception(self, request, exception):
        print(exception)
        return api_500(request)









