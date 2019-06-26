
from django.conf import settings
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.response import Response

import swiftclient

from collectionjson import services
from core.renderers import BinaryFileRenderer

from .models import UploadedFile, UploadedFileFilter, uploaded_file_path
from .serializers import UploadedFileSerializer
from .permissions import IsOwnerOrChris


class UploadedFileList(generics.ListCreateAPIView):
    """
    A view for the collection of uploaded user files.
    """
    queryset = UploadedFile.objects.all()
    serializer_class = UploadedFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the files
        owned by the currently authenticated user.
        """
        user = self.request.user
        # if the user is chris then return all the files in the sandboxed filesystem
        if (user.username == 'chris'):
            return UploadedFile.objects.all()
        return UploadedFile.objects.filter(owner=user)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner with the uploaded file before first
        saving to the DB.
        """
        request_data = serializer.context['request'].data
        path = '/'
        if 'upload_path' in request_data:
            path = request_data['upload_path']
        user = self.request.user
        path = serializer.validate_file_upload_path(path)
        serializer.save(owner=user, upload_path=path)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of instances for the queried plugin.
        A collection+json template is also added to the response.
        """
        response = super(UploadedFileList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('uploadedfile-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append write template
        template_data = {'upload_path': "", 'fname': ""}
        return services.append_collection_template(response, template_data)


class UploadedFileListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of uploaded files resulting from a query search.
    """
    serializer_class = UploadedFileSerializer
    queryset = UploadedFile.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = UploadedFileFilter


class UploadedFileDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A feed's file view.
    """
    queryset = UploadedFile.objects.all()
    serializer_class = UploadedFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(UploadedFileDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"upload_path": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to include the current fname in the request.
        """
        user_file = self.get_object()
        request.data['fname'] = user_file.fname.file # fname is required in the serializer
        return super(UploadedFileDetail, self).update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """
        Overriden to validate and update the upload path in swift.
        """
        request_data = serializer.context['request'].data
        path = request_data['upload_path']
        user_file = self.get_object()
        if path != user_file.upload_path:
            user = self.request.user
            path = serializer.validate_file_upload_path(path)
            serializer.save(owner=user, upload_path=path)
            # initiate a Swift service connection to delete the old object from swift
            conn = swiftclient.Connection(
                user=settings.SWIFT_USERNAME,
                key=settings.SWIFT_KEY,
                authurl=settings.SWIFT_AUTH_URL,
            )
            old_swift_path = uploaded_file_path(user_file, '')
            conn.delete_object(settings.SWIFT_CONTAINER_NAME, old_swift_path)

    def perform_destroy(self, instance):
        """
        Overriden to delete the file from swift storage.
        """
        swift_path = uploaded_file_path(instance, '')
        instance.delete()
        # initiate a Swift service connection to delete the object from swift
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, swift_path)


class UploadedFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource .
    """
    queryset = UploadedFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        user_file = self.get_object()
        return Response(user_file.fname)
