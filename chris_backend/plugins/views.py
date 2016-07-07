
from rest_framework import generics, permissions

from .models import Plugin, PluginParameter, PluginInstance, StringParameter
from .models import FloatParameter, IntParameter, BoolParameter
from .serializers import PluginSerializer,  PluginParameterSerializer
from .serializers import PluginInstanceSerializer, StringParameterSerializer
from .serializers import FloatParameterSerializer, IntParameterSerializer
from .serializers import BoolParameterSerializer
from .permissions import IsChrisOrReadOnly


class PluginList(generics.ListCreateAPIView):
    """
    A view for the collection of plugins.
    """
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class PluginDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A plugin view.
    """
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class PluginParameterDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A plugin parameter view.
    """
    serializer_class = PluginParameter
    queryset = PluginParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class PluginInstanceDetail(generics.RetrieveAPIView):
    """
    A plugin instance view.
    """
    serializer_class = PluginInstance
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class StringParameterDetail(generics.RetrieveAPIView):
    """
    A string parameter view.
    """
    serializer_class = StringParameter
    queryset = StringParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    

class IntParameterDetail(generics.RetrieveAPIView):
    """
    An integer parameter view.
    """
    serializer_class = IntParameter
    queryset = IntParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class FloatParameterDetail(generics.RetrieveAPIView):
    """
    A float parameter view.
    """
    serializer_class = FloatParameter
    queryset = IntParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    

class BoolParameterDetail(generics.RetrieveAPIView):
    """
    A boolean parameter view.
    """
    serializer_class = BoolParameter
    queryset = BoolParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
