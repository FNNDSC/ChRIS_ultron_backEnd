
from rest_framework import generics
from rest_framework import permissions
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from collectionjson import services
from core.renderers import BinaryFileRenderer
from plugins.models import Plugin

from .models import PluginInstance, PluginInstanceFilter
from .models import PluginInstanceFile, PluginInstanceFileFilter
from .models import StrParameter, FloatParameter, IntParameter
from .models import BoolParameter, PathParameter, UnextpathParameter
from .serializers import PARAMETER_SERIALIZERS
from .serializers import GenericParameterSerializer
from .serializers import PluginInstanceSerializer, PluginInstanceFileSerializer
from .permissions import IsRelatedFeedOwnerOrChris, IsOwnerOrChrisOrReadOnly


class PluginInstanceList(generics.ListCreateAPIView):
    """
    A view for the collection of plugin instances.
    """
    serializer_class = PluginInstanceSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        """
        Overriden to remove 'status' from the request as it must take the default
        value on creation.
        """
        self.request.data.pop('status', None)
        return super(PluginInstanceList, self).create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner, a plugin and a previous plugin instance with 
        the newly created plugin instance before first saving to the DB. All the plugin 
        instance's parameters in the request are also properly saved to the DB. Finally
        the plugin's app is run with the provided plugin instance's parameters.
        """
        user = self.request.user
        # get previous plugin instance and create the new plugin instance
        request_data = serializer.context['request'].data
        previous_id = request_data['previous_id'] if 'previous_id' in request_data else ""
        previous = serializer.validate_previous(previous_id)
        plugin = self.get_object()

        # collect and validate parameters from the request
        parameter_serializers = []
        parameters = plugin.parameters.all()
        for parameter in parameters:
            if parameter.name in request_data:
                data = {'value': request_data[parameter.name]}
                param_type = parameter.type
                if param_type in ('path', 'unextpath'):
                    # these serializers need the user to be passed
                    parameter_serializer = PARAMETER_SERIALIZERS[param_type](data=data,
                                                                             user=user)
                else:
                    parameter_serializer = PARAMETER_SERIALIZERS[param_type](data=data)
                parameter_serializer.is_valid(raise_exception=True)
                parameter_serializers.append((parameter, parameter_serializer))
            elif not parameter.optional:
                raise ValidationError({parameter.name: ["This field is required."]})

        # if no validation errors at this point then save to the DB
        plg_inst = serializer.save(owner=user, plugin=plugin, previous=previous,
                                   compute_resource=plugin.compute_resource)
        parameters_dict = {}
        for param, param_serializer in parameter_serializers:
            param_inst = param_serializer.save(plugin_inst=plg_inst, plugin_param=param)
            parameters_dict[param.name] = param_inst.value

        # run the plugin's app
        plg_inst.run(parameters_dict)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of instances for the queried plugin. A document-level
        link relation and a collection+json template are also added to the response.
        """
        queryset = self.get_plugin_instances_queryset()
        response = services.get_list_response(self, queryset)
        plugin = self.get_object()
        # append document-level link relations
        links = {'plugin': reverse('plugin-detail', request=request,
                                   kwargs={"pk": plugin.id})}
        response = services.append_collection_links(response, links)
        # append write template
        param_names = plugin.get_plugin_parameter_names()
        template_data = {'title': "", 'previous_id': "", 'cpu_limit': "",
                         'memory_limit': "", 'number_of_workers': "", 'gpu_limit': ""}
        for name in param_names:
            template_data[name] = ""
        return services.append_collection_template(response, template_data)

    def get_plugin_instances_queryset(self):
        """
        Custom method to get the actual plugin instances' queryset.
        """
        plugin = self.get_object()
        return self.filter_queryset(plugin.instances.all())


class AllPluginInstanceList(generics.ListAPIView):
    """
    A view for the collection of all plugin instances.
    """
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to add a query list and document-level link relation to the response.
        """
        response = super(AllPluginInstanceList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('allplugininstance-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'plugins': reverse('plugin-list', request=request)}
        return services.append_collection_links(response, links)


class AllPluginInstanceListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of plugin instances resulting from a query search.
    """
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PluginInstanceFilter

        
class PluginInstanceDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A plugin instance view.
    """
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to check a plugin's instance status.
        """
        instance = self.get_object()
        instance.check_exec_status()
        response = super(PluginInstanceDetail, self).retrieve(request, *args, **kwargs)
        template_data = {'title': '', 'status': ''}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove descriptors that are not allowed to be updated before
        serializer validation.
        """
        data = self.request.data
        data.pop('gpu_limit', None)
        data.pop('number_of_workers', None)
        data.pop('cpu_limit', None)
        data.pop('memory_limit', None)
        return super(PluginInstanceDetail, self).update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """
        Overriden to cancel this plugin instance and all its descendants' execution .
        """
        if 'status' in self.request.data:
            instance = self.get_object()
            descendants = instance.get_descendant_instances()
            for inst in descendants:
                inst.cancel()
        super(PluginInstanceDetail, self).perform_update(serializer)

    def destroy(self, request, *args, **kwargs):
        """
        Overriden to cancel the plugin instance execution before deleting it. All the
        descendant instances are also cancelled before they are deleted by the DB CASCADE.
        """
        instance = self.get_object()
        descendants = instance.get_descendant_instances()
        for inst in descendants:
            inst.cancel()
        return super(PluginInstanceDetail, self).destroy(request, *args, **kwargs)


class PluginInstanceDescendantList(generics.ListAPIView):
    """
    A view for the collection of plugin instances that are a descendant of this plugin
    instance.
    """
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the plugin instance descendants.
        """
        queryset = self.get_descendants_queryset()
        return services.get_list_response(self, queryset)

    def get_descendants_queryset(self):
        """
        Custom method to get the actual descendants queryset.
        """
        instance = self.get_object()
        return self.filter_queryset(instance.get_descendant_instances())


class PluginInstanceFileList(generics.ListAPIView):
    """
    A view for the collection of files written by a plugin instance.
    """
    serializer_class = PluginInstanceFileSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the files created by the queried plugin instance.
        Document-level link relations are also added to the response.
        """
        queryset = self.get_files_queryset()
        response = services.get_list_response(self, queryset)
        instance = self.get_object()
        feed = instance.feed
        links = {'feed': reverse('feed-detail', request=request,
                             kwargs={"pk": feed.id}),
                 'plugin_inst': reverse('plugininstance-detail', request=request,
                                                 kwargs={"pk": instance.id})}
        return services.append_collection_links(response, links)

    def get_files_queryset(self):
        """
        Custom method to get the actual files queryset.
        """
        instance = self.get_object()
        return self.filter_queryset(instance.files.all())


class AllPluginInstanceFileList(generics.ListAPIView):
    """
    A view for the collection of all plugin instance files written to all the feeds the
    the authenticated user owns.
    """
    serializer_class = PluginInstanceFileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to add a query list to the response.
        """
        response = super(AllPluginInstanceFileList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('allplugininstancefile-list-query-search', request=request)]
        return services.append_collection_querylist(response, query_list)

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the feed files
        written to feeds owned by the currently authenticated user.
        """
        user = self.request.user
        # if the user is chris then return all the files in the system
        if user.username == 'chris':
            return PluginInstanceFile.objects.all()
        return PluginInstanceFile.objects.filter(plugin_inst__feed__owner=user)


class AllPluginInstanceFileListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of plugin instance files written to all the feeds the
    the authenticated user owns and resulting from a query search.
    """
    serializer_class = PluginInstanceFileSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PluginInstanceFileFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the feed files
        written to feeds owned by the currently authenticated user.
        """
        user = self.request.user
        # if the user is chris then return all the files in the system
        if user.username == 'chris':
            return PluginInstanceFile.objects.all()
        return PluginInstanceFile.objects.filter(plugin_inst__feed__owner=user)


class PluginInstanceFileDetail(generics.RetrieveAPIView):
    """
    A view for a file written by a plugin instance.
    """
    queryset = PluginInstanceFile.objects.all()
    serializer_class = PluginInstanceFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris,)


class FileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource.
    """
    queryset = PluginInstanceFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris,)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        plg_inst_file = self.get_object()
        return Response(plg_inst_file.fname)


class PluginInstanceParameterList(generics.ListAPIView):
    """
    A view for the collection of parameters that the plugin instance was run with.
    """
    serializer_class = GenericParameterSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the parameter values used by the queried
        plugin instance.
        """
        queryset = self.get_parameters_queryset()
        return services.get_list_response(self, queryset)

    def get_parameters_queryset(self):
        """
        Custom method to get a queryset with all the parameters regardless of their type.
        """
        instance = self.get_object()
        return self.filter_queryset(instance.get_parameter_instances())


class StrParameterDetail(generics.RetrieveAPIView):
    """
    A string parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['string']
    queryset = StrParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    

class IntParameterDetail(generics.RetrieveAPIView):
    """
    An integer parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['integer']
    queryset = IntParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


class FloatParameterDetail(generics.RetrieveAPIView):
    """
    A float parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['float']
    queryset = FloatParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    

class BoolParameterDetail(generics.RetrieveAPIView):
    """
    A boolean parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['boolean']
    queryset = BoolParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


class PathParameterDetail(generics.RetrieveAPIView):
    """
    A path parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['path']
    queryset = PathParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


class UnextpathParameterDetail(generics.RetrieveAPIView):
    """
    A unextpath parameter view.
    """
    serializer_class = PARAMETER_SERIALIZERS['unextpath']
    queryset = UnextpathParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
