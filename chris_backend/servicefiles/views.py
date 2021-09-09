
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.response import Response

from collectionjson import services
from core.renderers import BinaryFileRenderer

from .models import ServiceFile, ServiceFileFilter
from .serializers import ServiceFileSerializer
from .permissions import IsChrisOrReadOnly


class ServiceFileList(generics.ListCreateAPIView):
    """
    A view for the collection of PACS files.
    """
    http_method_names = ['get', 'post']
    queryset = ServiceFile.objects.all()
    serializer_class = ServiceFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a collection+json
        template to the response.
        """
        response = super(ServiceFileList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('servicefile-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append write template
        template_data = {'path': "", 'service_name': ""}
        return services.append_collection_template(response, template_data)

    def create(self, request, *args, **kwargs):
        """
        Overriden to remove computed descriptors from the request if submitted.
        """
        self.request.data.pop('fname', None)
        return super(ServiceFileList, self).create(request, *args, **kwargs)


class ServiceFileListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of Service files resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = ServiceFileSerializer
    queryset = ServiceFile.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = ServiceFileFilter


class ServiceFileDetail(generics.RetrieveAPIView):
    """
    A Service file view.
    """
    http_method_names = ['get']
    queryset = ServiceFile.objects.all()
    serializer_class = ServiceFileSerializer
    permission_classes = (permissions.IsAuthenticated,)


class ServiceFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource .
    """
    http_method_names = ['get']
    queryset = ServiceFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        service_file = self.get_object()
        return Response(service_file.fname)
