
import logging
from pathlib import Path

from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, serializers
from rest_framework.reverse import reverse
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiTypes

from core.models import (ChrisFolder, FolderGroupPermission,
                         FolderGroupPermissionFilter, FolderUserPermission,
                         FolderUserPermissionFilter, ChrisFile, FileGroupPermission,
                         FileGroupPermissionFilter, FileUserPermission,
                         FileUserPermissionFilter, ChrisLinkFile,
                         LinkFileGroupPermission, LinkFileGroupPermissionFilter,
                         LinkFileUserPermission, LinkFileUserPermissionFilter)
from core.renderers import BinaryFileRenderer
from core.views import TokenAuthSupportQueryString
from collectionjson import services

from .serializers import (FileBrowserFolderSerializer,
                          FileBrowserFolderGroupPermissionSerializer,
                          FileBrowserFolderUserPermissionSerializer,
                          FileBrowserFileSerializer,
                          FileBrowserFileGroupPermissionSerializer,
                          FileBrowserFileUserPermissionSerializer,
                          FileBrowserLinkFileSerializer,
                          FileBrowserLinkFileGroupPermissionSerializer,
                          FileBrowserLinkFileUserPermissionSerializer)
from .services import (get_folder_queryset,
                       get_folder_children_queryset,
                       get_folder_files_queryset,
                       get_folder_link_files_queryset)
from .permissions import (IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly,
                          IsFolderOwnerOrChrisOrHasAnyFolderPermissionReadOnly,
                          IsFileOwnerOrChrisOrHasAnyFilePermissionReadOnly,
                          IsLinkFileOwnerOrChrisOrHasAnyLinkFilePermissionReadOnly)


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
        Overriden to return a custom queryset that is only comprised by the root
        folder (empty path).
        """
        if getattr(self, "swagger_fake_view", False):
            return ChrisFolder.objects.none()
        user = self.request.user
        pk_dict = {'path': ''}

        if user.is_authenticated:
            qs = get_folder_queryset(pk_dict, user)
        else:
            qs = get_folder_queryset(pk_dict)

        if not qs.exists():
            raise Http404('Not found.')
        return qs


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
        if getattr(self, "swagger_fake_view", False):
            return ChrisFolder.objects.none()

        user = self.request.user
        id = self.request.GET.get('id')
        pk_dict = {'id': id}

        if id is None:
            path = self.request.GET.get('path', '')
            path = path.strip('/')
            pk_dict = {'path': path}

        if user.is_authenticated:
            return get_folder_queryset(pk_dict, user)
        return get_folder_queryset(pk_dict)


class FileBrowserFolderDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A ChRIS folder view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserFolderSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to retrieve a file browser folder and append a collection+json template.
        """
        response = super(FileBrowserFolderDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"public": "", "path": ""}
        return services.append_collection_template(response, template_data)

    def destroy(self, request, *args, **kwargs):
        """
        Overriden to verify that the user's home or feeds folder is not being deleted.
        """
        username = request.user.username
        folder = self.get_object()
        path_parts = folder.path.split('/')

        if username != 'chris' and len(path_parts) > 1 and path_parts[0] == 'home':
            if len(path_parts) == 2 or (len(path_parts) == 3 and path_parts[2] == 'feeds'):

                raise serializers.ValidationError(
                    {'non_field_errors':
                         [f"Deleting folder '{folder.path}' is not allowed."]})

        return super(FileBrowserFolderDetail, self).destroy(request, *args, **kwargs)


class FileBrowserFolderChildList(generics.ListAPIView):
    """
    A view for the collection of folders that are the children of this folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserFolderSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the children folders and append document-level
        link relations.
        """
        user = request.user
        folder = self.get_object()

        if user.is_authenticated:
            children_qs = get_folder_children_queryset(folder, user)
        else:
            children_qs = get_folder_children_queryset(folder)

        response = services.get_list_response(self, children_qs)

        links = {'folder': reverse('chrisfolder-detail', request=request,
                                   kwargs={"pk": folder.id})}
        return services.append_collection_links(response, links)


class FileBrowserFolderGroupPermissionList(generics.ListCreateAPIView):
    """
    A view for a folder's collection of group permissions.
    """
    http_method_names = ['get', 'post']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserFolderGroupPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to provide a group and folder before first saving to the DB.
        """
        group = serializer.validated_data.pop('grp_name')
        folder = self.get_object()
        serializer.save(group=group, folder=folder)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the group permissions for the queried folder.
        A query list, document-level link relations and a collection+json template are
        also added to the response.
        """
        queryset = self.get_group_permissions_queryset()
        response = services.get_list_response(self, queryset)
        folder = self.get_object()

        query_list = [reverse('foldergrouppermission-list-query-search',
                              request=request, kwargs={"pk": folder.id})]
        response = services.append_collection_querylist(response, query_list)

        links = {'folder': reverse('chrisfolder-detail', request=request,
                                   kwargs={"pk": folder.id})}
        response = services.append_collection_links(response, links)

        template_data = {"grp_name": "", "permission": ""}
        return services.append_collection_template(response, template_data)

    def get_group_permissions_queryset(self):
        """
        Custom method to get the actual group permissions queryset for the folder.
        """
        folder = self.get_object()
        return FolderGroupPermission.objects.filter(folder=folder)


class FileBrowserFolderGroupPermissionListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of folder-specific group permissions resulting from a query
    search.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserFolderGroupPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)
    filterset_class = FolderGroupPermissionFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the folder-specific
        group permissions.
        """
        if getattr(self, "swagger_fake_view", False):
            return FolderGroupPermission.objects.none()
        folder = get_object_or_404(ChrisFolder, pk=self.kwargs['pk'])
        return FolderGroupPermission.objects.filter(folder=folder)


class FileBrowserFolderGroupPermissionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A view for a folder's group permission.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = FileBrowserFolderGroupPermissionSerializer
    queryset = FolderGroupPermission.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsFolderOwnerOrChrisOrHasAnyFolderPermissionReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FileBrowserFolderGroupPermissionDetail,
                         self).retrieve(request,*args, **kwargs)
        template_data = {"permission": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'grp_name' if provided by the user before serializer
        validation.
        """
        request.data.pop('grp_name', None)  # shoud not change on update
        return super(FileBrowserFolderGroupPermissionDetail, self).update(request,
                                                                          *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Overriden to remove the group permission for the link file in the SHARED folder
        pointing to the folder. The link file itself is removed if all its permissions
        have been removed.
        """
        folder = instance.folder
        group = instance.group

        lf = folder.get_shared_link()
        if lf is not None:
            lf.remove_group_permission(group, 'r')

            if not lf.shared_groups.all().exists() and not lf.shared_users.all().exists():
                folder.remove_shared_link()
        super(FileBrowserFolderGroupPermissionDetail, self).perform_destroy(instance)


class FileBrowserFolderUserPermissionList(generics.ListCreateAPIView):
    """
    A view for a folder's collection of user permissions.
    """
    http_method_names = ['get', 'post']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserFolderUserPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to provide a user and folder before first saving to the DB.
        """
        user = serializer.validated_data.pop('username')
        folder = self.get_object()
        serializer.save(user=user, folder=folder)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the user permissions for the queried folder.
        A query list, document-level link relations and a collection+json template are
        also added to the response.
        """
        queryset = self.get_user_permissions_queryset()
        response = services.get_list_response(self, queryset)
        folder = self.get_object()

        query_list = [reverse('folderuserpermission-list-query-search',
                              request=request, kwargs={"pk": folder.id})]
        response = services.append_collection_querylist(response, query_list)

        links = {'folder': reverse('chrisfolder-detail', request=request,
                                   kwargs={"pk": folder.id})}
        response = services.append_collection_links(response, links)

        template_data = {"username": "", "permission": ""}
        return services.append_collection_template(response, template_data)

    def get_user_permissions_queryset(self):
        """
        Custom method to get the actual user permissions queryset for the folder.
        """
        folder = self.get_object()
        return FolderUserPermission.objects.filter(folder=folder)


class FileBrowserFolderUserPermissionListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of folder-specific user permissions resulting from a query
    search.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserFolderUserPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)
    filterset_class = FolderUserPermissionFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the folder-specific
        user permissions.
        """
        if getattr(self, "swagger_fake_view", False):
            return FolderUserPermission.objects.none()
        folder = get_object_or_404(ChrisFolder, pk=self.kwargs['pk'])
        return FolderUserPermission.objects.filter(folder=folder)


class FileBrowserFolderUserPermissionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A view for a folder's user permission.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = FileBrowserFolderUserPermissionSerializer
    queryset = FolderUserPermission.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsFolderOwnerOrChrisOrHasAnyFolderPermissionReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FileBrowserFolderUserPermissionDetail,
                         self).retrieve(request,*args, **kwargs)
        template_data = {"permission": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'username' if provided by the user before serializer
        validation.
        """
        request.data.pop('username', None)  # shoud not change on update
        return super(FileBrowserFolderUserPermissionDetail, self).update(request,
                                                                          *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Overriden to remove the user permission for the link file in the SHARED folder
        pointing to the folder. The link file itself is removed if all its permissions
        have been removed.
        """
        folder = instance.folder
        user = instance.user

        lf = folder.get_shared_link()
        if lf is not None:
            lf.remove_user_permission(user, 'r')

            if not lf.shared_groups.all().exists() and not lf.shared_users.all().exists():
                folder.remove_shared_link()
        super(FileBrowserFolderUserPermissionDetail, self).perform_destroy(instance)


class FileBrowserFolderFileList(generics.ListAPIView):
    """
    A view for the collection of all the files directly under this folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserFileSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the files directly under this folder and
        append document-level link relations.
        """
        user = request.user
        folder = self.get_object()

        if user.is_authenticated:
            files_qs = get_folder_files_queryset(folder, user)
        else:
            files_qs = get_folder_files_queryset(folder)

        response = services.get_list_response(self, files_qs)

        links = {'folder': reverse('chrisfolder-detail', request=request,
                                   kwargs={"pk": folder.id})}
        return services.append_collection_links(response, links)


class FileBrowserFileDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A ChRIS file view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = ChrisFile.get_base_queryset()
    serializer_class = FileBrowserFileSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to retrieve a file and append a collection+json template.
        """
        response = super(FileBrowserFileDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"public": "", "new_file_path": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'fname' if provided by the user before serializer
        validation.
        """
        request.data.pop('fname', None)  # shoud not change on update
        return super(FileBrowserFileDetail, self).update(request, *args, **kwargs)


class FileBrowserFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource.
    """
    http_method_names = ['get']
    queryset = ChrisFile.get_base_queryset()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly)
    authentication_classes = (TokenAuthSupportQueryString, BasicAuthentication,
                              SessionAuthentication)

    @extend_schema(responses=OpenApiResponse(OpenApiTypes.BINARY))
    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        chris_file = self.get_object()
        f = chris_file.fname
        resp = FileResponse(f)
        resp['Content-Disposition'] = f'attachment; filename="{Path(f.name).name}"'
        return resp


class FileBrowserFileGroupPermissionList(generics.ListCreateAPIView):
    """
    A view for a file's collection of group permissions.
    """
    http_method_names = ['get', 'post']
    queryset = ChrisFile.objects.all()
    serializer_class = FileBrowserFileGroupPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to provide a group and file before first saving to the DB.
        """
        group = serializer.validated_data.pop('grp_name')
        f = self.get_object()
        serializer.save(group=group, file=f)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the group permissions for the queried file.
        A query list, document-level link relations and a collection+json template are
        also added to the response.
        """
        queryset = self.get_group_permissions_queryset()
        response = services.get_list_response(self, queryset)
        f = self.get_object()

        query_list = [reverse('filegrouppermission-list-query-search',
                              request=request, kwargs={"pk": f.id})]
        response = services.append_collection_querylist(response, query_list)

        links = {'file': reverse('chrisfile-detail', request=request,
                                   kwargs={"pk": f.id})}
        response = services.append_collection_links(response, links)

        template_data = {"grp_name": "", "permission": ""}
        return services.append_collection_template(response, template_data)

    def get_group_permissions_queryset(self):
        """
        Custom method to get the actual group permissions queryset for the file.
        """
        f = self.get_object()
        return FileGroupPermission.objects.filter(file=f)


class FileBrowserFileGroupPermissionListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of file-specific group permissions resulting from a query
    search.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserFileGroupPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)
    filterset_class = FileGroupPermissionFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the file-specific
        group permissions.
        """
        if getattr(self, "swagger_fake_view", False):
            return FileGroupPermission.objects.none()
        f = get_object_or_404(ChrisFile, pk=self.kwargs['pk'])
        return FileGroupPermission.objects.filter(file=f)


class FileBrowserFileGroupPermissionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A view for a file's group permission.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = FileBrowserFileGroupPermissionSerializer
    queryset = FileGroupPermission.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsFileOwnerOrChrisOrHasAnyFilePermissionReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FileBrowserFileGroupPermissionDetail,
                         self).retrieve(request,*args, **kwargs)
        template_data = {"permission": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'grp_name' if provided by the user before serializer
        validation.
        """
        request.data.pop('grp_name', None)  # shoud not change on update
        return super(FileBrowserFileGroupPermissionDetail, self).update(request,
                                                                          *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Overriden to remove the group permission for the link file in the SHARED folder
        pointing to the file. The link file itself is removed if all its permissions
        have been removed.
        """
        f = instance.file
        group = instance.group

        lf = f.get_shared_link()
        if lf is not None:
            lf.remove_group_permission(group, 'r')

            if not lf.shared_groups.all().exists() and not lf.shared_users.all().exists():
                f.remove_shared_link()
        super(FileBrowserFileGroupPermissionDetail, self).perform_destroy(instance)


class FileBrowserFileUserPermissionList(generics.ListCreateAPIView):
    """
    A view for a file's collection of user permissions.
    """
    http_method_names = ['get', 'post']
    queryset = ChrisFile.objects.all()
    serializer_class = FileBrowserFileUserPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to provide a user and file before first saving to the DB.
        """
        user = serializer.validated_data.pop('username')
        f = self.get_object()
        serializer.save(user=user, file=f)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the user permissions for the queried file.
        A query list, document-level link relations and a collection+json template are
        also added to the response.
        """
        queryset = self.get_user_permissions_queryset()
        response = services.get_list_response(self, queryset)
        f = self.get_object()

        query_list = [reverse('fileuserpermission-list-query-search',
                              request=request, kwargs={"pk": f.id})]
        response = services.append_collection_querylist(response, query_list)

        links = {'file': reverse('chrisfile-detail', request=request,
                                 kwargs={"pk": f.id})}
        response = services.append_collection_links(response, links)

        template_data = {"username": "" , "permission": ""}
        return services.append_collection_template(response, template_data)

    def get_user_permissions_queryset(self):
        """
        Custom method to get the actual user permissions queryset for the file.
        """
        f = self.get_object()
        return FileUserPermission.objects.filter(file=f)


class FileBrowserFileUserPermissionListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of file-specific user permissions resulting from a query
    search.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserFileUserPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)
    filterset_class = FileUserPermissionFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the file-specific
        user permissions.
        """
        if getattr(self, "swagger_fake_view", False):
            return FileUserPermission.objects.none()
        f = get_object_or_404(ChrisFile, pk=self.kwargs['pk'])
        return FileUserPermission.objects.filter(file=f)


class FileBrowserFileUserPermissionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A view for a file's user permission.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = FileBrowserFileUserPermissionSerializer
    queryset = FileUserPermission.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsFileOwnerOrChrisOrHasAnyFilePermissionReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FileBrowserFileUserPermissionDetail,
                         self).retrieve(request,*args, **kwargs)
        template_data = {"permission": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'username' if provided by the user before serializer
        validation.
        """
        request.data.pop('username', None)  # shoud not change on update
        return super(FileBrowserFileUserPermissionDetail, self).update(request,
                                                                          *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Overriden to remove the user permission for the link file in the SHARED folder
        pointing to the file. The link file itself is removed if all its permissions
        have been removed.
        """
        f = instance.file
        user = instance.user

        lf = f.get_shared_link()
        if lf is not None:
            lf.remove_user_permission(user, 'r')

            if not lf.shared_groups.all().exists() and not lf.shared_users.all().exists():
                f.remove_shared_link()
        super(FileBrowserFileUserPermissionDetail, self).perform_destroy(instance)


class FileBrowserFolderLinkFileList(generics.ListAPIView):
    """
    A view for the collection of all the ChRIS link files directly under this folder.
    """
    http_method_names = ['get']
    queryset = ChrisFolder.objects.all()
    serializer_class = FileBrowserLinkFileSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the files directly under this folder and
        append document-level link relations.
        """
        user = request.user
        folder = self.get_object()

        if user.is_authenticated:
            link_files_qs = get_folder_link_files_queryset(folder, user)
        else:
            link_files_qs = get_folder_link_files_queryset(folder)

        response = services.get_list_response(self, link_files_qs)

        links = {'folder': reverse('chrisfolder-detail', request=request,
                                   kwargs={"pk": folder.id})}
        return services.append_collection_links(response, links)


class FileBrowserLinkFileDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A ChRIS link file view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = ChrisLinkFile.objects.all()
    serializer_class = FileBrowserLinkFileSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to retrieve a link file and append a collection+json template.
        """
        response = super(FileBrowserLinkFileDetail, self).retrieve(request, *args,
                                                                  **kwargs)
        template_data = {"public": "", "new_link_file_path": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'fname' and 'path' if provided by the user before serializer
        validation.
        """
        request.data.pop('fname', None)  # shoud not change on update
        request.data.pop('path', None)  # shoud not change on update
        return super(FileBrowserLinkFileDetail, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Overriden to verify that the user's home's system-predefined link files are not
        being deleted.
        """
        username = request.user.username
        lf = self.get_object()
        fname_parts = lf.fname.name.split('/')

        if username != 'chris' and len(fname_parts) == 3 and fname_parts[0] == 'home' and (
                fname_parts[2] in ('public.chrislink', 'shared.chrislink')):

            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"Deleting link file '{lf.fname.name}' is not allowed."]})

        return super(FileBrowserLinkFileDetail, self).destroy(request, *args, **kwargs)


class FileBrowserLinkFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource.
    """
    http_method_names = ['get']
    queryset = ChrisLinkFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrCanWriteOrCanReadOnlyOrPublicReadOnly)
    authentication_classes = (TokenAuthSupportQueryString, BasicAuthentication,
                              SessionAuthentication)

    @extend_schema(responses=OpenApiResponse(OpenApiTypes.BINARY))
    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        chris_link_file = self.get_object()
        f = chris_link_file.fname
        resp = FileResponse(f)
        resp['Content-Disposition'] = f'attachment; filename="{Path(f.name).name}"'
        return resp


class FileBrowserLinkFileGroupPermissionList(generics.ListCreateAPIView):
    """
    A view for a link file's collection of group permissions.
    """
    http_method_names = ['get', 'post']
    queryset = ChrisLinkFile.objects.all()
    serializer_class = FileBrowserLinkFileGroupPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to provide a group and link file before first saving to the DB.
        """
        group = serializer.validated_data.pop('grp_name')
        lf = self.get_object()
        serializer.save(group=group, link_file=lf)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the group permissions for the queried link file.
        A query list, document-level link relations and a collection+json template are
        also added to the response.
        """
        queryset = self.get_group_permissions_queryset()
        response = services.get_list_response(self, queryset)
        lf = self.get_object()

        query_list = [reverse('linkfilegrouppermission-list-query-search',
                              request=request, kwargs={"pk": lf.id})]
        response = services.append_collection_querylist(response, query_list)

        links = {'link_file': reverse('chrislinkfile-detail', request=request,
                                      kwargs={"pk": lf.id})}
        response = services.append_collection_links(response, links)

        template_data = {"grp_name": "", "permission": ""}
        return services.append_collection_template(response, template_data)

    def get_group_permissions_queryset(self):
        """
        Custom method to get the actual group permissions queryset for the link file.
        """
        lf = self.get_object()
        return LinkFileGroupPermission.objects.filter(link_file=lf)


class FileBrowserLinkFileGroupPermissionListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of link file-specific group permissions resulting from a
    query search.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserLinkFileGroupPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)
    filterset_class = LinkFileGroupPermissionFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the link file-specific
        group permissions.
        """
        if getattr(self, "swagger_fake_view", False):
            return LinkFileGroupPermission.objects.none()
        lf = get_object_or_404(ChrisLinkFile, pk=self.kwargs['pk'])
        return LinkFileGroupPermission.objects.filter(link_file=lf)


class FileBrowserLinkFileGroupPermissionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A view for a link file's group permission.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = FileBrowserLinkFileGroupPermissionSerializer
    queryset = LinkFileGroupPermission.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsLinkFileOwnerOrChrisOrHasAnyLinkFilePermissionReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FileBrowserLinkFileGroupPermissionDetail,
                         self).retrieve(request,*args, **kwargs)
        template_data = {"permission": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'grp_name' if provided by the user before serializer
        validation.
        """
        request.data.pop('grp_name', None)  # shoud not change on update
        return super(FileBrowserLinkFileGroupPermissionDetail, self).update(request,
                                                                          *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Overriden to remove the group permission for the link file in the SHARED folder
        pointing to this link file. The link file itself is removed if all its
        permissions have been removed.
        """
        link_file = instance.link_file
        group = instance.group

        lf = link_file.get_shared_link()
        if lf is not None:
            lf.remove_group_permission(group, 'r')

            if not lf.shared_groups.all().exists() and not lf.shared_users.all().exists():
                link_file.remove_shared_link()
        super(FileBrowserLinkFileGroupPermissionDetail, self).perform_destroy(instance)


class FileBrowserLinkFileUserPermissionList(generics.ListCreateAPIView):
    """
    A view for a link file's collection of user permissions.
    """
    http_method_names = ['get', 'post']
    queryset = ChrisLinkFile.objects.all()
    serializer_class = FileBrowserLinkFileUserPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to provide a user and link file before first saving to the DB.
        """
        user = serializer.validated_data.pop('username')
        lf = self.get_object()
        serializer.save(user=user, link_file=lf)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the user permissions for the queried link file.
        A query list, document-level link relations and a collection+json template are
        also added to the response.
        """
        queryset = self.get_user_permissions_queryset()
        response = services.get_list_response(self, queryset)
        lf = self.get_object()

        query_list = [reverse('linkfileuserpermission-list-query-search',
                              request=request, kwargs={"pk": lf.id})]
        response = services.append_collection_querylist(response, query_list)

        links = {'link_file': reverse('chrislinkfile-detail', request=request,
                                      kwargs={"pk": lf.id})}
        response = services.append_collection_links(response, links)

        template_data = {"username": "", "permission": ""}
        return services.append_collection_template(response, template_data)

    def get_user_permissions_queryset(self):
        """
        Custom method to get the actual user permissions queryset for the link file.
        """
        lf = self.get_object()
        return LinkFileUserPermission.objects.filter(link_file=lf)


class FileBrowserLinkFileUserPermissionListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of link file-specific user permissions resulting from a
    query search.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserLinkFileUserPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasAnyPermissionReadOnly)
    filterset_class = LinkFileUserPermissionFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the link file-specific
        user permissions.
        """
        if getattr(self, "swagger_fake_view", False):
            return LinkFileUserPermission.objects.none()
        lf = get_object_or_404(ChrisLinkFile, pk=self.kwargs['pk'])
        return LinkFileUserPermission.objects.filter(link_file=lf)


class FileBrowserLinkFileUserPermissionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A view for a link file's user permission.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = FileBrowserLinkFileUserPermissionSerializer
    queryset = LinkFileUserPermission.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsLinkFileOwnerOrChrisOrHasAnyLinkFilePermissionReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FileBrowserLinkFileUserPermissionDetail,
                         self).retrieve(request,*args, **kwargs)
        template_data = {"permission": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'username' if provided by the user before serializer
        validation.
        """
        request.data.pop('username', None)  # shoud not change on update
        return super(FileBrowserLinkFileUserPermissionDetail, self).update(request,
                                                                          *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Overriden to remove the user permission for the link file in the SHARED folder
        pointing to this link file. The link file itself is removed if all its
        permissions have been removed.
        """
        link_file = instance.link_file
        user = instance.user

        lf = link_file.get_shared_link()
        if lf is not None:
            lf.remove_user_permission(user, 'r')

            if not lf.shared_groups.all().exists() and not lf.shared_users.all().exists():
                link_file.remove_shared_link()
        super(FileBrowserLinkFileUserPermissionDetail, self).perform_destroy(instance)
