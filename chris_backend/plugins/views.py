
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services

from .models import Plugin, PluginFilter, PluginParameter 
from .models import PluginInstance, PluginInstanceFilter
from .models import StringParameter, FloatParameter, IntParameter
from .models import BoolParameter, PathParameter

from .serializers import PARAMETER_SERIALIZERS
from .serializers import PluginSerializer,  PluginParameterSerializer
from .serializers import PluginInstanceSerializer
from .permissions import IsChrisOrReadOnly
from .services.manager import PluginManager


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
        # append query list
        query_list = [reverse('plugin-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'feeds': reverse('feed-list', request=request)}    
        return services.append_collection_links(response, links)


class PluginListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of plugins resulting from a query search.
    """
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    filter_class = PluginFilter
        

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
        return services.append_collection_links(response, links)

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
        if 'previous_id' in request_data:
            previous_id = request_data['previous_id']
        previous = serializer.validate_previous(previous_id, plugin)
        gpu_limit = 0
        if request_data.get('gpu_limit'):
            gpu_limit = serializer.validate_gpu_limit(request_data['gpu_limit'], plugin)
        # create plugin instance with corresponding owner, plugin and previous instances
        plugin_inst = serializer.save(owner=self.request.user, plugin=plugin,
                                      previous=previous)
        # collect parameters from the request and validate and save them to the DB 
        parameters = plugin.parameters.all()
        parameters_dict = {}
        for parameter in parameters:
            if parameter.name in request_data:
                requested_value = request_data[parameter.name]
                data = {'value': requested_value}
                parameter_serializer = PARAMETER_SERIALIZERS[parameter.type](data=data)
                parameter_serializer.is_valid(raise_exception=True)
                if parameter.name == 'gpu_limit':
                    requested_value = serializer.validate_gpu_limit(request_data['gpu_limit'], plugin)
                parameter_serializer.save(plugin_inst=plugin_inst, plugin_param=parameter)
                parameters_dict[parameter.name] = requested_value
        # run the plugin's app
        pl_manager = PluginManager()
        pl_manager.run_plugin_app(  plugin_inst, 
                                    parameters_dict,
                                    service             = 'pfcon',
                                    inputDirOverride    = '/share/incoming',
                                    outputDirOverride   = '/share/outgoing',
                                    IOPhost             = 'host',
                                    gpu_limit = gpu_limit
                                    )

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of instances for the queried plugin.
        A collection+json template is also added to the response.
        """
        queryset = self.get_plugin_instances_queryset()
        response = services.get_list_response(self, queryset)
        plugin = self.get_object()
        # append query list
        query_list = [reverse('plugininstance-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'plugin': reverse('plugin-detail', request=request,
                                   kwargs={"pk": plugin.id})}
        response = services.append_collection_links(response, links)
        # append write template
        param_names = plugin.get_plugin_parameter_names()
        template_data = {'previous_id': ""}
        for name in param_names:
            template_data[name] = ""
        return services.append_collection_template(response, template_data)

    def get_plugin_instances_queryset(self):
        """
        Custom method to get the actual plugin instances' queryset.
        """
        plugin = self.get_object()
        return self.filter_queryset(plugin.instances.all())


class PluginInstanceListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of plugin instances resulting from a query search.
    """
    serializer_class = PluginInstanceSerializer
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    filter_class = PluginInstanceFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the plugin  
        instances owned by the currently authenticated user.
        """
        user = self.request.user
        # if the user is chris then return all the plugin instances in the system
        if user.username == 'chris':
            return PluginInstance.objects.all()
        return PluginInstance.objects.filter(owner=user)

        
class PluginInstanceDetail(generics.RetrieveAPIView):
    """
    A plugin instance view.
    """
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overloaded method to check a plugin's instance status.
        """
        instance = self.get_object()
        pl_manager = PluginManager()
        pl_manager.check_plugin_app_exec_status(instance)
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
    queryset = FloatParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)
    

class BoolParameterDetail(generics.RetrieveAPIView):
    """
    A boolean parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['boolean']
    queryset = BoolParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)


class PathParameterDetail(generics.RetrieveAPIView):
    """
    A path parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['path']
    queryset = PathParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsChrisOrReadOnly,)