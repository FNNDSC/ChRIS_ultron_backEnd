
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services

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

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a collection+json
        template to the response.
        """
        response = super(PluginList, self).list(request, *args, **kwargs)
        links = {'feeds': reverse('feed-list', request=request)}    
        response = services.append_collection_links(request, response, links)
        template_data = {"name": "", "type": ""} 
        return services.append_collection_template(response, template_data)


class PluginDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A plugin view.
    """
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(PluginDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"name": "", "type": ""} 
        return services.append_collection_template(response, template_data)


class PluginParameterList(generics.ListCreateAPIView):
    """
    A view for the collection of plugin parameters.
    """
    serializer_class = PluginParameterSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)

    def perform_create(self, serializer):
        """
        Overriden to associate a plugin with the newly created parameter
        before first saving to the DB.
        """
        serializer.save(plugin=self.get_object())

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of parameters for the queried plugin.
        A collection+json template is also added to the response.
        """
        queryset = self.get_plugin_parameters_queryset()
        response = services.get_list_response(self, queryset)
        plugin = self.get_object()
        links = {'plugin': reverse('plugin-detail', request=request,
                                   kwargs={"pk": plugin.id})}    
        response = services.append_collection_links(request, response, links)
        template_data = {"name": "", "optional": False, "type": ""} 
        return services.append_collection_template(response, template_data)

    def get_plugin_parameters_queryset(self):
        """
        Custom method to get the actual plugin parameters' queryset.
        """
        plugin = self.get_object()
        return self.filter_queryset(plugin.parameters.all())

    
class PluginParameterDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A plugin parameter view.
    """
    serializer_class = PluginParameterSerializer
    queryset = PluginParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(PluginParameterDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"name": "", "optional": False, "type": ""} 
        return services.append_collection_template(response, template_data)


class PluginInstanceList(generics.ListCreateAPIView):
    """
    A view for the collection of plugin instances.
    """
    serializer_class = PluginInstanceSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner and a plugin with the newly created 
        plugin instance before first saving to the DB.
        """
        serializer.save(owner=[self.request.user], plugin=self.get_object())

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of instances for the queried plugin.
        A collection+json template is also added to the response.
        """
        queryset = self.get_plugin_instances_queryset()
        response = services.get_list_response(self, queryset)
        plugin = self.get_object()
        links = {'plugin': reverse('plugin-detail', request=request,
                                   kwargs={"pk": plugin.id})}
        response = services.append_collection_links(request, response, links)
        param_names = self.get_plugin_parameter_names()
        template_data = {}
        for name in param_names:
            template_data[name] = ""
        return services.append_collection_template(response, template_data)

    def get_plugin_instances_queryset(self):
        """
        Custom method to get the actual plugin instances' queryset.
        """
        plugin = self.get_object()
        return self.filter_queryset(plugin.instances.all())

    def get_plugin_parameter_names(self):
        """
        Custom method to get the list of plugin parameter names.
        """
        plugin = self.get_object()
        params = plugin.parameters.all()
        return [param.name for param in params]

        
class PluginInstanceDetail(generics.RetrieveAPIView):
    """
    A plugin instance view.
    """
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class StringParameterDetail(generics.RetrieveAPIView):
    """
    A string parameter view.
    """
    serializer_class = StringParameterSerializer
    queryset = StringParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    

class IntParameterDetail(generics.RetrieveAPIView):
    """
    An integer parameter view.
    """
    serializer_class = IntParameterSerializer
    queryset = IntParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class FloatParameterDetail(generics.RetrieveAPIView):
    """
    A float parameter view.
    """
    serializer_class = FloatParameterSerializer
    queryset = IntParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    

class BoolParameterDetail(generics.RetrieveAPIView):
    """
    A boolean parameter view.
    """
    serializer_class = BoolParameterSerializer
    queryset = BoolParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
