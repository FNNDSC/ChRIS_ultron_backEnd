
import logging

from django.http import FileResponse
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services
from core.renderers import BinaryFileRenderer

from .permissions import IsOwnerOrChris
from .models import ChrisInstance, ChrisFolder, ChrisLinkFile
from .serializers import ChrisInstanceSerializer, ChrisLinkFileSerializer


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
