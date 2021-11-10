
from django.http import Http404
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import filter_files_by_n_slashes
from .serializers import FileBrowserPathListSerializer, FileBrowserPathSerializer
from .services import (get_path_folders, get_path_file_serializer_class,
                       get_path_file_queryset)


class FileBrowserPathList(generics.ListAPIView):
    """
    A view for the initial page of the collection of file browser paths.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserPathListSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a query list to the response.
        """
        response = super(FileBrowserPathList, self).list(request, *args, **kwargs)
        # append query list
        query_url = reverse('filebrowserpath-list-query-search', request=request)
        data = [{'name': 'path', 'value': ''}]
        queries = [{'href': query_url, 'rel': 'search', 'data': data}]
        response.data['queries'] = queries
        return response

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the two initial
        folders.
        """
        username = self.request.user.username
        objects = [{'path': '', 'subfolders': f'SERVICES,{username}'}]
        return self.filter_queryset(objects)


class FileBrowserPathListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of file browser paths resulting from a query search.
    """
    http_method_names = ['get']
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        """
        Overriden to return a custom queryset.
        """
        username = self.request.user.username
        path = self.request.GET.get('path', '')
        if not path:
            objects = [{'path': '', 'subfolders': f'SERVICES,{username}'}]
        else:
            path = path.strip('/')
            try:
                subfolders = get_path_folders(path, username)
            except ValueError:
                objects = []
            else:
                objects = [{'path': path, 'subfolders': ','.join(subfolders)}]
        return self.filter_queryset(objects)

    def get_serializer_class(self, *args, **kwargs):
        """
        Overriden to return the serializer class that should be used for serializing
        output.
        """
        path = self.request.GET.get('path', '')
        if not path:
            return FileBrowserPathListSerializer
        self.kwargs['path'] = path.strip('/')
        return FileBrowserPathSerializer


class FileBrowserPath(APIView):
    """
    A file browser path view.
    """
    http_method_names = ['get']
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        username = request.user.username
        path = kwargs.get('path')
        try:
            subfolders = get_path_folders(path, username)
        except ValueError:
            raise Http404('Not found.')
        object = {'path': path, 'subfolders': ','.join(subfolders)}
        serializer = self.get_serializer(object)
        return Response(serializer.data)

    def get_serializer(self, *args, **kwargs):
        """
        Return the serializer instance that should be used for serializing output.
        """
        kwargs.setdefault('context', self.get_serializer_context())
        return FileBrowserPathSerializer(*args, **kwargs)

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {'request': self.request, 'view': self}


class FileBrowserPathFileList(generics.ListAPIView):
    """
    A view for the collection of a file browser path's files.
    """
    http_method_names = ['get']
    permission_classes = (permissions.IsAuthenticated, )

    def get_queryset(self):
        """
        Overriden to return a custom queryset.
        """
        username = self.request.user.username
        path = self.kwargs.get('path')
        try:
            qs = get_path_file_queryset(path, username)
        except ValueError:
            raise Http404('Not found.')
        n_slashes = path.count('/') + 1
        return filter_files_by_n_slashes(qs, str(n_slashes))

    def get_serializer_class(self):
        """
        Overriden to return the serializer class that should be used for serializing
        output.
        """
        username = self.request.user.username
        path = self.kwargs.get('path')
        return get_path_file_serializer_class(path, username)
