
from rest_framework import generics, permissions

from .models import Plugin
from .serializers import PluginSerializer
from .permissions import IsChrisOrReadOnly


class PluginList(generics.ListCreateAPIView):
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class PluginDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
