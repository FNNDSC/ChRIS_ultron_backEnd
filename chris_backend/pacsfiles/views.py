
from django.http import FileResponse
from django.contrib.auth.models import User, Group
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiTypes

from collectionjson import services
from core.renderers import BinaryFileRenderer
from core.models import ChrisFolder
from core.views import TokenAuthSupportQueryString
from .models import (PACS, PACSFilter, PACSSeries, PACSSeriesFilter, PACSFile,
                     PACSFileFilter)
from .serializers import PACSSerializer, PACSSeriesSerializer, PACSFileSerializer
from .services import PfdcmClient
from .permissions import IsChrisOrIsPACSUserReadOnly


class PACSList(generics.ListCreateAPIView):
    """
    A view for the collection of registered PACS.
    """
    http_method_names = ['get']
    serializer_class = PACSSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a query list to the response.
        """
        response = super(PACSList, self).list(request, *args, **kwargs)

        # append query list
        query_list = [reverse('pacs-list-query-search', request=request)]
        return services.append_collection_querylist(response, query_list)

    def get_queryset(self):
        """
        Overriden to contact pfdcm for new PACS available. New PACS might be created
        with a POST request in the future but this is an initial implementation so no
        changes are required to other backend services (oxidicom for instance).
        """
        queryset = PACS.objects.all()
        existing_pacs_names_set = {pacs.identifier for pacs in queryset}

        pfdcm_cl = PfdcmClient()
        pfdcm_pacs_names_set = set(pfdcm_cl.get_pacs_list())

        active_pacs_set = existing_pacs_names_set.intersection(pfdcm_pacs_names_set)

        # handle differences between the set of PACS in CUBE and PFDCM

        for pacs in queryset:
            if pacs.identifier in active_pacs_set and not pacs.active:
                pacs.active = True
                pacs.save()
            elif pacs.identifier not in active_pacs_set and pacs.active:
                pacs.active = False
                pacs.save()

        new_pacs_names = pfdcm_pacs_names_set.difference(existing_pacs_names_set)

        if new_pacs_names:
            (pacs_grp, _) = Group.objects.get_or_create(name='pacs_users')
            chris_user = User.objects.get(username='chris')

            for name in new_pacs_names:
                folder_path = f'SERVICES/PACS/{name}'
                (pacs_folder, tf) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                      owner=chris_user)
                if tf:
                    pacs_folder.grant_group_permission(pacs_grp, 'r')

                PACS.objects.create(folder=pacs_folder, identifier=name)
        return PACS.objects.all()


class PACSListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of PACS resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = PACSSerializer
    queryset = PACS.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)
    filterset_class = PACSFilter


class PACSDetail(generics.RetrieveAPIView):
    """
    A PACS view.
    """
    http_method_names = ['get']
    queryset = PACS.objects.all()
    serializer_class = PACSSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)


class PACSSpecificSeriesList(generics.ListAPIView):
    """
    A view for the collection of PACS-specific series.
    """
    http_method_names = ['get']
    queryset = PACS.objects.all()
    serializer_class = PACSSeriesSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the PACS series for the queried PACS.
        """
        queryset = self.get_pacs_series_queryset()
        response = services.get_list_response(self, queryset)
        pacs = self.get_object()
        links = {'pacs': reverse('pacs-detail', request=request,
                                 kwargs={"pk": pacs.id})}
        return services.append_collection_links(response, links)

    def get_pacs_series_queryset(self):
        """
        Custom method to get the actual PACS series queryset.
        """
        pacs = self.get_object()
        return self.filter_queryset(pacs.series_list.all())


class PACSSeriesList(generics.ListCreateAPIView):
    """
    A view for the collection of all PACS Series.
    """
    http_method_names = ['get', 'post']
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
