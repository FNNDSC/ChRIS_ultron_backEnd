
from rest_framework import generics, permissions

from .models import ChrisInstance
from .serializers import ChrisInstanceSerializer


class ChrisInstanceDetail(generics.RetrieveAPIView):
    """
    A compute resource view.
    """
    serializer_class = ChrisInstanceSerializer
    queryset = ChrisInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
