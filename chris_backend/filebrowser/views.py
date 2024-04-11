
import logging

from django.http import Http404, FileResponse
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from core.models import ChrisFolder, ChrisFile, ChrisLinkFile
from core.renderers import BinaryFileRenderer
from core.views import TokenAuthSupportQueryString
from collectionjson import services

from .serializers import (FileBrowserFolderSerializer, FileBrowserChrisFileSerializer,
                          FileBrowserChrisLinkFileSerializer)
from .services import (get_authenticated_user_folder_queryset,
                       get_unauthenticated_user_folder_queryset,
                       get_authenticated_user_folder_children,
                       get_unauthenticated_user_folder_children)
from .permissions import (IsOwnerOrChrisOrReadOnly,
                          IsOwnerOrChrisOrRelatedFeedOwnerOrPublicReadOnly)


logger = logging.getLogger(__name__)


class FileBrowserFolderList(generics.ListCreateAPIView):
    """
    A view for the initial page of the collection of file browser folders. The returned
    collection only has a single element.
    """
    http_method_names = ['get', 'post']
    serializer_class = FileBrowserFolderSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner with the folder before first saving to the DB.
        """
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a query list and a collection+json template to the response.
        """
        response = super(FileBrowserFolderList, self).list(request, *args, **kwargs)
        # append query list
        query_url = reverse('chrisfolder-list-query-search', request=request)
        data = [{'name': 'id', 'value': ''}, {'name': 'path', 'value': ''}]
        queries = [{'href': query_url, 'rel': 'search', 'data': data}]
        response.data['queries'] = queries

        # append write template
        template_data = {'path': ''}
        return services.append_collection_template(response, template_data)

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the initial
        path (empty path).
        """
        return ChrisFolder.objects.filter(path='')


class FileBrowserFolderListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of file browser folders resulting from a query search.
    The returned collection only has at most one element.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserFolderSerializer

    def get_queryset(self):
        """
        Overriden to return a custom queryset of at most one element.
        """
        user = self.request.user
        id = self.request.GET.get('id')
        pk_dict = {'id': id}
        if id is None:
            path = self.request.GET.get('path', '')
            path = path.strip('/')
            pk_dict = {'path': path}
        if user.is_authenticated:
            return get_authenticated_user_folder_queryset(pk_dict, user)
        return get_unauthenticated_user_folder_queryset(pk_dict)


class FileBrowserFolderDetail(generics.RetrieveDestroyAPIView):
    """
    A ChRIS folder view.
    """
    http_method_names = ['get', 'delete']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserFolderSerializer
    permission_classes = (IsOwnerOrChrisOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to get the collection of file browser paths directly under a path.
        """
        user = request.user
        id = kwargs.get('pk')
        pk_dict = {'id': id}

        if user.is_authenticated:
            qs = get_authenticated_user_folder_queryset(pk_dict, user)
        else:
            qs = get_unauthenticated_user_folder_queryset(pk_dict)

        if qs.count() == 0:
            raise Http404('Not found.')

        return super(FileBrowserFolderDetail, self).retrieve(request, *args, **kwargs)

class FileBrowserFolderChildList(generics.ListAPIView):
    """
    A view for the collection of folders that are the children of this folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserFolderSerializer

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the children ChRIS folders.
        """
        user = request.user
        id = kwargs.get('pk')
        pk_dict = {'id': id}

        if user.is_authenticated:
            qs = get_authenticated_user_folder_queryset(pk_dict, user)
        else:
            qs = get_unauthenticated_user_folder_queryset(pk_dict)

        if qs.count() == 0:
            raise Http404('Not found.')

        queryset = self.get_children_queryset()
        return services.get_list_response(self, queryset)

    def get_children_queryset(self):
        """
        Custom method to get the actual queryset of the children.
        """
        user = self.request.user
        folder = self.get_object()
        if user.is_authenticated:
            children = get_authenticated_user_folder_children(folder, user)
        else:
            children = get_unauthenticated_user_folder_children(folder)
        return self.filter_queryset(children)


class FileBrowserFolderFileList(generics.ListAPIView):
    """
    A view for the collection of all the files directly under this folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserChrisFileSerializer

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the files directly under this folder.
        """
        user = request.user
        id = kwargs.get('pk')
        pk_dict = {'id': id}

        if user.is_authenticated:
            qs = get_authenticated_user_folder_queryset(pk_dict, user)
        else:
            qs = get_unauthenticated_user_folder_queryset(pk_dict)

        if qs.count() == 0:
            raise Http404('Not found.')

        queryset = self.get_files_queryset()
        response = services.get_list_response(self, queryset)
        return response

    def get_files_queryset(self):
        """
        Custom method to get a queryset with all the files directly under this folder.
        """
        folder = self.get_object()
        return folder.chris_files.all()


class FileBrowserFileDetail(generics.RetrieveAPIView):
    """
    A ChRIS file view.
    """
    http_method_names = ['get']
    queryset = ChrisFile.get_base_queryset()
    serializer_class = FileBrowserChrisFileSerializer
    permission_classes = (IsOwnerOrChrisOrRelatedFeedOwnerOrPublicReadOnly,)


class FileBrowserFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource.
    """
    http_method_names = ['get']
    queryset = ChrisFile.get_base_queryset()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (IsOwnerOrChrisOrRelatedFeedOwnerOrPublicReadOnly,)
    authentication_classes = (TokenAuthSupportQueryString, BasicAuthentication,
                              SessionAuthentication)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        chris_file = self.get_object()
        return FileResponse(chris_file.fname)


class FileBrowserFolderLinkFileList(generics.ListAPIView):
    """
    A view for the collection of all the ChRIS link files directly under this folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserChrisLinkFileSerializer

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the link files directly under this folder.
        """
        user = request.user
        id = kwargs.get('pk')
        pk_dict = {'id': id}

        if user.is_authenticated:
            qs = get_authenticated_user_folder_queryset(pk_dict, user)
        else:
            qs = get_unauthenticated_user_folder_queryset(pk_dict)

        if qs.count() == 0:
            raise Http404('Not found.')

        queryset = self.get_link_files_queryset()
        response = services.get_list_response(self, queryset)
        return response

    def get_link_files_queryset(self):
        """
        Custom method to get a queryset with all the link files directly under this
        folder.
        """
        folder = self.get_object()
        return folder.chris_link_files.all()


class FileBrowserLinkFileDetail(generics.RetrieveAPIView):
    """
    A ChRIS link file view.
    """
    http_method_names = ['get']
    queryset = ChrisLinkFile.objects.all()
    serializer_class = FileBrowserChrisLinkFileSerializer
    permission_classes = (IsOwnerOrChrisOrRelatedFeedOwnerOrPublicReadOnly,)


class FileBrowserLinkFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource.
    """
    http_method_names = ['get']
    queryset = ChrisLinkFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (IsOwnerOrChrisOrRelatedFeedOwnerOrPublicReadOnly,)
    authentication_classes = (TokenAuthSupportQueryString, BasicAuthentication,
                              SessionAuthentication)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        chris_link_file = self.get_object()
        return FileResponse(chris_link_file.fname)
