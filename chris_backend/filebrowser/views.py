
import json

from django.http import Http404
from rest_framework import generics
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import filter_files_by_n_slashes
from .serializers import (FileBrowserPathListSerializer, FileBrowserPathSerializer,
                          FileBrowserPathFileSerializer)
from .services import (get_path_folders, get_path_file_queryset,
                       get_path_file_model_class,
                       get_unauthenticated_user_path_folders,
                       get_unauthenticated_user_path_file_queryset)


class FileBrowserPathList(generics.ListAPIView):
    """
    A view for the initial page of the collection of file browser paths. The returned
    collection only has a single element.
    """
    http_method_names = ['get']
    serializer_class = FileBrowserPathListSerializer

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
        Overriden to return a custom queryset that is only comprised by the initial
        path (empty path).
        """
        user = self.request.user
        path = ''
        if user.is_authenticated:
            subfolders = get_path_folders(path, user)
        else:
            subfolders = get_unauthenticated_user_path_folders(path)
        objects = [{'path': '', 'subfolders': json.dumps(subfolders)}]
        return self.filter_queryset(objects)


class FileBrowserPathListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of file browser paths resulting from a query search.
    The returned collection only has at most one element.
    """
    http_method_names = ['get']

    def get_queryset(self):
        """
        Overriden to return a custom queryset.
        """
        user = self.request.user
        path = self.request.GET.get('path', '')
        path = path.strip('/')
        try:
            if user.is_authenticated:
                subfolders = get_path_folders(path, user)  # already sorted
            else:
                subfolders = get_unauthenticated_user_path_folders(path)
        except ValueError:
            objects = []
        else:
            objects = [{'path': path, 'subfolders': json.dumps(subfolders)}]
        return self.filter_queryset(objects)

    def get_serializer_class(self, *args, **kwargs):
        """
        Overriden to return the serializer class that should be used for serializing
        output.
        """
        path = self.request.GET.get('path', '')
        path = path.strip('/')
        if not path:
            return FileBrowserPathListSerializer
        self.kwargs['path'] = path
        return FileBrowserPathSerializer


class FileBrowserPath(APIView):
    """
    A file browser path view.
    """
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        user = request.user
        path = kwargs.get('path')
        try:
            if user.is_authenticated:
                subfolders = get_path_folders(path, user)  # already sorted
            else:
                subfolders = get_unauthenticated_user_path_folders(path)
        except ValueError:
            raise Http404('Not found.')
        object = {'path': path, 'subfolders': json.dumps(subfolders)}
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

    def get_queryset(self):
        """
        Overriden to return a custom queryset.
        """
        user = self.request.user
        path = self.kwargs.get('path')
        try:
            if user.is_authenticated:
                qs = get_path_file_queryset(path, user)
            else:
                qs = get_unauthenticated_user_path_file_queryset(path)
        except ValueError:
            raise Http404('Not found.')
        n_slashes = path.count('/') + 1
        return filter_files_by_n_slashes(qs, str(n_slashes))

    def get_serializer_class(self):
        """
        Overriden to return the serializer class that should be used for serializing
        output.
        """
        path = self.kwargs.get('path')
        model_class = get_path_file_model_class(path)
        FileBrowserPathFileSerializer.Meta.model = model_class
        return FileBrowserPathFileSerializer
