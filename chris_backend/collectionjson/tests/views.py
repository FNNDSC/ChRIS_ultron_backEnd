from six.moves.urllib.parse import urljoin

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet, ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ParseError

from collectionjson.renderers import CollectionJsonRenderer
from collectionjson.parsers import CollectionJsonParser

from .models import Dummy, Person, Employee, EmployeeFilter, Simple
from .serializers import EmployeeHyperlinkedModelSerializer, PersonHyperlinkedModelSerializer
from .serializers import DummyHyperlinkedModelSerializer, SimpleModelSerializer


class EmployeeModelViewSet(ModelViewSet):
    renderer_classes = (CollectionJsonRenderer, )
    parser_classes = (CollectionJsonParser, )
    queryset = Employee.objects.all()
    serializer_class = EmployeeHyperlinkedModelSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = EmployeeFilter
    

class EmployeeReadOnlyModelViewSet(ReadOnlyModelViewSet):
    renderer_classes = (CollectionJsonRenderer, )
    queryset = Employee.objects.all()
    serializer_class = EmployeeHyperlinkedModelSerializer


class PersonReadOnlyModelViewSet(ReadOnlyModelViewSet):
    renderer_classes = (CollectionJsonRenderer, )
    queryset = Person.objects.all()
    serializer_class = PersonHyperlinkedModelSerializer


class DummyReadOnlyModelViewSet(ReadOnlyModelViewSet):
    renderer_classes = (CollectionJsonRenderer, )
    queryset = Dummy.objects.all()
    serializer_class = DummyHyperlinkedModelSerializer
    

class SimpleViewSet(ReadOnlyModelViewSet):
    renderer_classes = (CollectionJsonRenderer, )
    queryset = Simple.objects.all()
    serializer_class = SimpleModelSerializer


class NoSerializerView(APIView):
    renderer_classes = (CollectionJsonRenderer, )

    def get(self, request):
        return Response({'foo': '1'})


class PaginatedDataView(APIView):
    renderer_classes = (CollectionJsonRenderer, )

    def get(self, request):
        return Response({
            'next': 'http://test.com/colleciton/next',
            'previous': 'http://test.com/colleciton/previous',
            'results': [{'foo': 1}],
        })
    

class NonePaginatedDataView(APIView):
    renderer_classes = (CollectionJsonRenderer, )

    def get(self, request):
        return Response({
            'next': None,
            'previous': None,
            'results': [{'foo': 1}],
        })    


class ParseErrorView(APIView):
    renderer_classes = (CollectionJsonRenderer, )

    def get(self, request):
        raise ParseError('lol nice one')


class UrlRewriteRenderer(CollectionJsonRenderer):
    def get_href(self, request):
        return urljoin('http://rewritten.com', request.path)
    

class UrlRewriteView(APIView):
    renderer_classes = (UrlRewriteRenderer, )

    def get(self, request):
        return Response({'foo': 'bar'})
    

class EmptyView(APIView):
    renderer_classes = (CollectionJsonRenderer, )

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)
