
from django.http import FileResponse
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiTypes

from collectionjson import services
from core.renderers import BinaryFileRenderer
from core.views import TokenAuthSupportQueryString
from .models import PACSSeries, PACSSeriesFilter, PACSFile, PACSFileFilter
from .serializers import PACSSeriesSerializer, PACSFileSerializer
from .permissions import IsChrisOrIsPACSUserReadOnly


class PACSSeriesList(generics.ListCreateAPIView):
    """
    A view for the collection of PACS Series.
    """
    http_method_names = ['get']
    queryset = PACSSeries.objects.all()
    serializer_class = PACSSeriesSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a query list and a collection+json template to the response.
        """
        response = super(PACSSeriesList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('pacsseries-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append write template
        template_data = {'path': '', 'ndicom': '', 'PatientID': '', 'PatientName': '',
                         'PatientBirthDate': '', 'PatientAge': '', 'PatientSex': '',
                         'StudyDate': '', 'AccessionNumber': '', 'Modality': '',
                         'ProtocolName': '', 'StudyInstanceUID': '',
                         'StudyDescription': '', 'SeriesInstanceUID': '',
                         'SeriesDescription': '', 'pacs_name': ''}
        return services.append_collection_template(response, template_data)

    def perform_create(self, serializer):
        """
        Overriden to associate the owner (chris user) with the PACS files for the Series
        before first saving to the DB.
        """
        serializer.save(owner=self.request.user)


class PACSSeriesListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of PACS Series resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = PACSSeriesSerializer
    queryset = PACSSeries.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)
    filterset_class = PACSSeriesFilter


class PACSSeriesDetail(generics.RetrieveAPIView):
    """
    A PACS Series view.
    """
    http_method_names = ['get']
    queryset = PACSSeries.objects.all()
    serializer_class = PACSSeriesSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)


class PACSFileList(generics.ListAPIView):
    """
    A view for the collection of PACS files.
    """
    http_method_names = ['get']
    queryset = PACSFile.get_base_queryset()
    serializer_class = PACSFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a query list to the
        response.
        """
        response = super(PACSFileList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('pacsfile-list-query-search', request=request)]
        return services.append_collection_querylist(response, query_list)


class PACSFileListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of PACS files resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = PACSFileSerializer
    queryset = PACSFile.get_base_queryset()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)
    filterset_class = PACSFileFilter


class PACSFileDetail(generics.RetrieveAPIView):
    """
    A PACS file view.
    """
    http_method_names = ['get']
    queryset = PACSFile.get_base_queryset()
    serializer_class = PACSFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)


class PACSFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource .
    """
    http_method_names = ['get']
    queryset = PACSFile.get_base_queryset()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)
    authentication_classes = (TokenAuthSupportQueryString, BasicAuthentication,
                              SessionAuthentication)

    @extend_schema(responses=OpenApiResponse(OpenApiTypes.BINARY))
    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        pacs_file = self.get_object()
        return FileResponse(pacs_file.fname)
