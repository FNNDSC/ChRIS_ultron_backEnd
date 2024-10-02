
from django.http import FileResponse

from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiTypes

from collectionjson import services
from core.renderers import BinaryFileRenderer
from core.views import TokenAuthSupportQueryString
from .models import UserFile, UserFileFilter
from .serializers import UserFileSerializer
from .permissions import IsOwnerOrChris


class UserFileList(generics.ListCreateAPIView):
    """
    A view for the collection of user files.
    """
    http_method_names = ['get', 'post']
    serializer_class = UserFileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the files
        owned by the currently authenticated user.
        """
        if getattr(self, "swagger_fake_view", False):
            return UserFile.objects.none()

        user = self.request.user

        # if the user is chris then return all the files in the user space
        if user.username == 'chris':
            return UserFile.get_base_queryset()

        return UserFile.get_base_queryset().filter(owner=user)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner with the file before first saving to the DB.
        """
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a query list and a collection+json template to the response.
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
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = UserFileFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the files
        owned by the currently authenticated user.
        """
        if getattr(self, "swagger_fake_view", False):
            return UserFile.objects.none()
        user = self.request.user

        # if the user is chris then return all the files in the user space
        if user.username == 'chris':
            return UserFile.get_base_queryset()

        return UserFile.get_base_queryset().filter(owner=user)


class UserFileDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A user file view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = UserFile.get_base_queryset()
    serializer_class = UserFileSerializer
    permission_classes = (IsOwnerOrChris,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(UserFileDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"upload_path": "", "public": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove 'fname' if provided by the user before serializer
        validation.
        """
        request.data.pop('fname', None)  # shoud not change on update
        return super(UserFileDetail, self).update(request, *args, **kwargs)


class UserFileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource.
    """
    http_method_names = ['get']
    queryset = UserFile.get_base_queryset()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (IsOwnerOrChris,)
    authentication_classes = (TokenAuthSupportQueryString, BasicAuthentication,
                              SessionAuthentication)

    @extend_schema(responses=OpenApiResponse(OpenApiTypes.BINARY))
    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        user_file = self.get_object()
        return FileResponse(user_file.fname)
