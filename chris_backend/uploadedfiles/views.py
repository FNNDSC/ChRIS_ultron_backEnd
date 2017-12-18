
from rest_framework import generics, permissions
from rest_framework.response import Response

from collectionjson import services
from core.renderers import BinaryFileRenderer

from .models import UploadedFile
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
        path = serializer.validate_file_upload_path(user, path)
        serializer.save(owner=user, upload_path=path)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of instances for the queried plugin.
        A collection+json template is also added to the response.
        """
        response = super(UploadedFileList, self).list(request, *args, **kwargs)
        # append write template
        template_data = {'upload_path': "", 'fname': ""}
        return services.append_collection_template(response, template_data)


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


