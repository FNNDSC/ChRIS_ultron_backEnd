
import logging

from django.http import FileResponse
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services
from core.renderers import BinaryFileRenderer

from userfiles.serializers import UserFileSerializer
from pacsfiles.serializers import PACSFileSerializer
from servicefiles.serializers import ServiceFileSerializer
from pipelines.serializers import PipelineSourceFileSerializer

from .permissions import IsOwnerOrChris
from .models import ChrisInstance, ChrisFolder, ChrisFolderFilter, ChrisLinkFile
from .serializers import (ChrisInstanceSerializer, ChrisFolderSerializer,
                          ChrisLinkFileSerializer)


logger = logging.getLogger(__name__)


class ChrisInstanceDetail(generics.RetrieveAPIView):
    """
    A compute resource view.
    """
    http_method_names = ['get']
    serializer_class = ChrisInstanceSerializer
    queryset = ChrisInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        """
        Overriden to return the ChrisInstance singleton.
        """
        return ChrisInstance.load()


class ChrisFolderList(generics.ListCreateAPIView):
    """
    A view for the collection of ChRIS folders.
    """
    http_method_names = ['get', 'post']
    queryset = ChrisFolder.objects.all()
    serializer_class = ChrisFolderSerializer
    permission_classes = (permissions.IsAuthenticated,)

    '''
    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the files
        owned by the currently authenticated user.
        """
        user = self.request.user
        # if the user is chris then return all the folders in the system
        #if user.username == 'chris':
        #    return ChrisFolder.objects.all()
        #return ChrisFolder.objects.filter(owner=user)
    '''

    def perform_create(self, serializer):
        """
        Overriden to associate an owner with the file before first saving to the DB.
        """
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations, a query list and a
        collection+json template to the response.
        """
        response = super(ChrisFolderList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('chrisfolder-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append write template
        template_data = {'path': ''}
        return services.append_collection_template(response, template_data)


class ChrisFolderListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of folders resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = ChrisFolderSerializer
    queryset = ChrisFolder.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = ChrisFolderFilter


class ChrisFolderDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A ChRIS folder view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = ChrisFolder.objects.all()
    serializer_class = ChrisFolderSerializer
    permission_classes = (permissions.IsAuthenticated,)
    #permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(ChrisFolderDetail, self).retrieve(request, *args, **kwargs)
        template_data = {'path': ''}
        return services.append_collection_template(response, template_data)

    def get_serializer(self, *args, **kwargs):
        """
        Overriden to remove hypermedia links from the serialized output (allows for
        more efficient clients).
        """
        obj = self.get_object()
        serializer = super(ChrisFolderDetail, self).get_serializer(*args, **kwargs)
        if obj.user_files.count() == 0:
            serializer.fields.pop('user_files')
        if obj.pacs_files.count() == 0:
            serializer.fields.pop('pacs_files')
        if obj.service_files.count() == 0:
            serializer.fields.pop('service_files')
        if obj.pipeline_source_files.count() == 0:
            serializer.fields.pop('pipeline_source_files')
        if obj.chris_link_files.count() == 0:
            serializer.fields.pop('chris_link_files')
        return serializer

class ChrisFolderChildList(generics.ListAPIView):
    """
    A view for the collection of ChRIS folders that are the children of this ChRIS
    folder.
    """
    http_method_names = ['get']
    serializer_class = ChrisFolderSerializer
    queryset = ChrisFolder.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the children ChRIS folders.
        """
        queryset = self.get_children_queryset()
        return services.get_list_response(self, queryset)

    def get_children_queryset(self):
        """
        Custom method to get the actual queryset of the children.
        """
        folder = self.get_object()
        return folder.children.all()


class ChrisFolderUserFileList(generics.ListAPIView):
    """
    A view for the collection of all the user files directly under this ChRIS folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = UserFileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the user files directly under this folder.
        """
        queryset = self.get_user_files_queryset()
        response = services.get_list_response(self, queryset)
        return response

    def get_user_files_queryset(self):
        """
        Custom method to get a queryset with all the user files directly under this
        folder.
        """
        folder = self.get_object()
        return folder.user_files.all()


class ChrisFolderPACSFileList(generics.ListAPIView):
    """
    A view for the collection of all the PACS files directly under this ChRIS folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = PACSFileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the PACS files directly under this folder.
        """
        queryset = self.get_pacs_files_queryset()
        response = services.get_list_response(self, queryset)
        return response

    def get_pacs_files_queryset(self):
        """
        Custom method to get a queryset with all the PACS files directly under this
        folder.
        """
        folder = self.get_object()
        return folder.pacs_files.all()


class ChrisFolderServiceFileList(generics.ListAPIView):
    """
    A view for the collection of all the service files directly under this ChRIS folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = ServiceFileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the service files directly under this folder.
        """
        queryset = self.get_service_files_queryset()
        response = services.get_list_response(self, queryset)
        return response

    def get_service_files_queryset(self):
        """
        Custom method to get a queryset with all the service files directly under this
        folder.
        """
        folder = self.get_object()
        return folder.service_files.all()


class ChrisFolderPipelineSourceFileList(generics.ListAPIView):
    """
    A view for the collection of all the pipeline source files directly under this
    ChRIS folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = PipelineSourceFileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the pipeline source files directly under
        this folder.
        """
        queryset = self.get_pipeline_source_files_queryset()
        response = services.get_list_response(self, queryset)
        return response

    def get_pipeline_source_files_queryset(self):
        """
        Custom method to get a queryset with all the pipeline source files directly
        under this folder.
        """
        folder = self.get_object()
        return folder.pipeline_source_files.all()


class ChrisLinkFileList(generics.ListAPIView):
    """
    A view for the collection of ChRIS link files within a folder.
    """
    http_method_names = ['get']
    serializer_class = ChrisLinkFileSerializer
    queryset = ChrisFolder.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the ChRIS links created within a folder.
        Document-level link relations are also added to the response.
        """
        queryset = self.get_chris_link_files_queryset()
        response = services.get_list_response(self, queryset)
        folder = self.get_object()
        links = {'parent_folder': reverse('chrisfolder-detail',
                                          request=request, kwargs={"pk": folder.id})}
        return services.append_collection_links(response, links)

    def get_chris_link_files_queryset(self):
        """
        Custom method to get the actual ChRIS links queryset.
        """
        folder = self.get_object()
        return self.filter_queryset(folder.chris_link_files.all())


class ChrisLinkFileDetail(generics.RetrieveAPIView):
    """
    A ChRIS link view.
    """
    http_method_names = ['get']
    queryset = ChrisLinkFile.objects.all()
    serializer_class = ChrisLinkFileSerializer
    permission_classes = (permissions.IsAuthenticated,)


class ChrisLinkFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource.
    """
    http_method_names = ['get']
    queryset = ChrisLinkFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        chris_link_file = self.get_object()
        return FileResponse(chris_link_file.fname)
