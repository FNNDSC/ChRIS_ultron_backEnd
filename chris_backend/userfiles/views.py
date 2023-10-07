
import logging

from django.conf import settings
from django.http import FileResponse
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services
from core.renderers import BinaryFileRenderer
from core.storage import connect_storage

from .models import UserFile, UserFileFilter
from .serializers import UserFileSerializer
from .permissions import IsOwnerOrChris


logger = logging.getLogger(__name__)


class UserFileList(generics.ListCreateAPIView):
    """
    A view for the collection of user files.
    """
    http_method_names = ['get', 'post']
    queryset = UserFile.objects.all()
    serializer_class = UserFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the files
        owned by the currently authenticated user.
        """
        user = self.request.user
        # if the user is chris then return all the files in the sandboxed filesystem
        if user.username == 'chris':
            return UserFile.objects.all()
        return UserFile.objects.filter(owner=user)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner with the file before first saving to the DB.
        """
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a collection+json
        template to the response.
        """
        response = super(UserFileList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('userfile-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append write template
        template_data = {'upload_path': "", 'fname': ""}
        return services.append_collection_template(response, template_data)


class UserFileListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of user files resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = UserFileSerializer
    queryset = UserFile.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = UserFileFilter


class UserFileDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A user file view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = UserFile.objects.all()
    serializer_class = UserFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(UserFileDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"upload_path": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to include the current fname in the request.
        """
        user_file = self.get_object()
        request.data['fname'] = user_file.fname.file  # fname required in the serializer
        return super(UserFileDetail, self).update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """
        Overriden to delete the old path from storage.
        """
        user_file = self.get_object()
        old_storage_path = user_file.fname.name
        serializer.save()
        storage_manager = connect_storage(settings)
        try:
            storage_manager.delete_obj(old_storage_path)
        except Exception as e:
            logger.error('Storage error, detail: %s' % str(e))

    def perform_destroy(self, instance):
        """
        Overriden to delete the file from storage.
        """
        storage_path = instance.fname.name
        instance.delete()
        storage_manager = connect_storage(settings)
        try:
            storage_manager.delete_obj(storage_path)
        except Exception as e:
            logger.error('Storage error, detail: %s' % str(e))


class UserFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource .
    """
    http_method_names = ['get']
    queryset = UserFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        user_file = self.get_object()
        return FileResponse(user_file.fname)
