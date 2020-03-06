
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.response import Response

from collectionjson import services
from core.renderers import BinaryFileRenderer

from .models import PACSFile, PACSFileFilter
from .serializers import PACSFileSerializer
from .permissions import IsChrisOrReadOnly


class PACSFileList(generics.ListCreateAPIView):
    """
    A view for the collection of PACS files.
    """
    queryset = PACSFile.objects.all()
    serializer_class = PACSFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a collection+json
        template to the response.
        """
        response = super(PACSFileList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('pacsfile-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append write template
        template_data = {'path': ""}
        return services.append_collection_template(response, template_data)

    def create(self, request, *args, **kwargs):
        """
        Overriden to remove computed descriptors from the request if submitted.
        """
        self.request.data.pop('fname', None)
        self.request.data.pop('mrn', None)
        self.request.data.pop('patient_name', None)
        self.request.data.pop('study', None)
        self.request.data.pop('series', None)
        self.request.data.pop('name', None)
        return super(PACSFileList, self).create(request, *args, **kwargs)


class PACSFileListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of PACS files resulting from a query search.
    """
    serializer_class = PACSFileSerializer
    queryset = PACSFile.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PACSFileFilter


class PACSFileDetail(generics.RetrieveAPIView):
    """
    A PACS file view.
    """
    queryset = PACSFile.objects.all()
    serializer_class = PACSFileSerializer
    permission_classes = (permissions.IsAuthenticated,)


class PACSFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource .
    """
    queryset = PACSFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        pacs_file = self.get_object()
        return Response(pacs_file.fname)
