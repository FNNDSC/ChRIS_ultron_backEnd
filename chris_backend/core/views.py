
from rest_framework import generics, permissions

from .models import ChrisInstance
from .serializers import ChrisInstanceSerializer


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
