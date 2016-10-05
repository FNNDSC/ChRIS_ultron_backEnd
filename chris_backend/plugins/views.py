
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services

from .models import Plugin, PluginParameter, PluginInstance, StringParameter
from .models import FloatParameter, IntParameter, BoolParameter

from .serializers import PARAMETER_SERIALIZERS
from .serializers import PluginSerializer,  PluginParameterSerializer
from .serializers import PluginInstanceSerializer
from .permissions import IsChrisOrReadOnly
from .services.manager import PluginManager

from .services import charm

import  socket
# This will need to be better addressed!
class pman_settings():
    HOST    =  [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
    PORT    = '5010'

class PluginList(generics.ListAPIView):
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
        return services.append_collection_links(request, response, links)


class PluginDetail(generics.RetrieveAPIView):
    """
    A plugin view.
    """
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class PluginParameterList(generics.ListAPIView):
    """
    A view for the collection of plugin parameters.
    """
    serializer_class = PluginParameterSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of parameters for the queried plugin.
        A document-level link relation is also added to the response.
        """
        queryset = self.get_plugin_parameters_queryset()
        response = services.get_list_response(self, queryset)
        plugin = self.get_object()
        links = {'plugin': reverse('plugin-detail', request=request,
                                   kwargs={"pk": plugin.id})}    
        return services.append_collection_links(request, response, links)

    def get_plugin_parameters_queryset(self):
        """
        Custom method to get the actual plugin parameters' queryset.
        """
        plugin = self.get_object()
        return self.filter_queryset(plugin.parameters.all())

    
class PluginParameterDetail(generics.RetrieveAPIView):
    """
    A plugin parameter view.
    """
    serializer_class = PluginParameterSerializer
    queryset = PluginParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class PluginInstanceList(generics.ListCreateAPIView):
    """
    A view for the collection of plugin instances.
    """
    serializer_class = PluginInstanceSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner, a plugin and a previous plugin instance with 
        the newly created plugin instance before first saving to the DB. All the plugin 
        instace's parameters in the resquest are also properly saved to the DB. Finally
        the plugin's app is run with the provided plugin instance's parameters.
        """
        plugin = self.get_object()
        request_data = serializer.context['request'].data
        # get previous plugin instance
        previous_id = ""
        if 'previous' in request_data:
            previous_id = request_data['previous']
        previous = serializer.validate_previous(previous_id, plugin)
        # create plugin instance with corresponding owner, plugin and previous instances
        plugin_inst = serializer.save(owner=self.request.user, plugin=plugin,
                                      previous=previous)
        # collect parameters from the request and validate and save them to the DB 
        parameters = plugin.parameters.all()
        parameters_dict = {}
        for parameter in parameters:
            if parameter.name in request_data:
                data = {'value': request_data[parameter.name]}
                parameter_serializer = PARAMETER_SERIALIZERS[parameter.type](data=data)
                parameter_serializer.is_valid(raise_exception=True)
                parameter_serializer.save(plugin_inst=plugin_inst, plugin_param=parameter)
                parameters_dict[parameter.name] = request_data[parameter.name]
        # run the plugin's app
        pl_manager = PluginManager()
        pl_manager.run_plugin_app(plugin_inst, parameters_dict)

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
        template_data = {'previous': ""}
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

    def retrieve(self, request, *args, **kwargs):
        """
        Overwritten method -- connect to pman to determine job status.

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        instance = self.get_object()

        instance.status = 'whatever'
        instance.save()

        # chris2pman   = charm.Charm(
        #     plugin_inst = instance
        # )
        #
        # if status is finished and not yet_register_outputfiles():
        #     register_outputfile()
        #     yet_register_outputfiles(true)


        serializer = self.get_serializer(instance)
        response = super(PluginInstanceDetail, self).retrieve(request, *args, **kwargs)

        return  response

class StringParameterDetail(generics.RetrieveAPIView):
    """
    A string parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['string']
    queryset = StringParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    

class IntParameterDetail(generics.RetrieveAPIView):
    """
    An integer parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['integer']
    queryset = IntParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class FloatParameterDetail(generics.RetrieveAPIView):
    """
    A float parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['float']
    queryset = IntParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    

class BoolParameterDetail(generics.RetrieveAPIView):
    """
    A boolean parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['boolean']
    queryset = BoolParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
