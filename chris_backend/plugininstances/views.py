
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.response import Response

from collectionjson import services
from core.renderers import BinaryFileRenderer

from plugins.models import Plugin, Pipeline
from .models import PluginInstance, PluginInstanceFilter, PluginInstanceFile
from .models import StrParameter, FloatParameter, IntParameter
from .models import BoolParameter, PathParameter
from .models import PipelineInstance, PipelineInstanceFilter
from .serializers import PARAMETER_SERIALIZERS
from .serializers import GenericParameterSerializer
from .serializers import PluginInstanceSerializer, PluginInstanceFileSerializer
from .serializers import PipelineInstanceSerializer
from .permissions import IsRelatedFeedOwnerOrChris
from .services.manager import PluginAppManager


class PipelineInstanceList(generics.ListCreateAPIView):
    """
    A view for the collection of pipeline instances.
    """
    serializer_class = PipelineInstanceSerializer
    queryset = Pipeline.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner, a plugin and a previous plugin instance with
        the newly created plugin instance before first saving to the DB. All the plugin
        instance's parameters in the request are also properly saved to the DB. Finally
        the plugin's app is run with the provided plugin instance's parameters.
        """
        # get previous plugin instance and create the new plugin instance
        request_data = serializer.context['request'].data
        previous_plugin_inst_id = request_data['previous_plugin_inst_id'] \
            if 'previous_plugin_inst_id' in request_data else None
        previous_plugin_inst = serializer.validate_previous_plugin_inst(
            previous_plugin_inst_id)
        pipeline = self.get_object()
        self.pipeline_inst = serializer.save(pipeline=pipeline)
        self.parsed_parameters = serializer.parse_parameters(request_data)
        # create associated plugin instances and save them to the DB in the same
        # tree order as the pipings in the pipeline
        pipings_tree = pipeline.get_pipings_tree()
        tree = pipings_tree['tree']
        root_id = pipings_tree['root_id']
        root_pip = tree[root_id]
        plugin_inst = self.create_plugin_inst(root_pip, previous_plugin_inst)
        # breath-first traversal
        plugin_inst_queue = [plugin_inst]
        pip_id_queue = [root_id]
        while len(pip_id_queue):
            curr_id = pip_id_queue.pop(0)
            curr_plugin_inst = plugin_inst_queue.pop(0)
            child_ids = tree[curr_id]['child_ids']
            for id in child_ids:
                pip = tree[id]['piping']
                plugin_inst = self.create_plugin_inst(pip, curr_plugin_inst)
                pip_id_queue.append(id)
                plugin_inst_queue.append(plugin_inst)

        # run the plugin's app
        # PluginAppManager.run_pipeline_instance(pipeline_inst,
        #                                 parameters_dict,
        #                                 service='pfcon',
        #                                 inputDirOverride='/share/incoming',
        #                                 outputDirOverride='/share/outgoing')

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of pipeline instances for the queried pipeline.
        A document-level link relation, query list and a collection+json template are
        also added to the response.
        """
        queryset = self.get_pipeline_instances_queryset()
        response = services.get_list_response(self, queryset)
        pipeline = self.get_object()
        # append query list
        query_list = [reverse('pipelineinstance-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'pipeline': reverse('pipeline-detail', request=request,
                                   kwargs={"pk": pipeline.id})}
        response = services.append_collection_links(response, links)
        # append write template
        template_data = {'previous_plugin_inst_id': "", 'title': "", 'description': ""}
        param_names = pipeline.get_pipings_parameters_names()
        for name in param_names:
            template_data[name] = ""
        return services.append_collection_template(response, template_data)

    def get_pipeline_instances_queryset(self):
        """
        Custom method to get the actual pipeline instances' queryset.
        """
        pipeline = self.get_object()
        return self.filter_queryset(pipeline.instances.all())

    def create_plugin_inst(self, piping, previous_inst):
        """
        Custom method to get the actual pipeline instances' queryset.
        """
        owner = self.request.user
        plugin_inst = PluginInstance()
        plugin_inst.pipeline_inst = self.pipeline_inst
        plugin_inst.owner = owner
        plugin_inst.plugin = piping.plugin
        plugin_inst.previous = previous_inst
        plugin_inst.compute_resource = piping.plugin.compute_resource
        plugin_inst.save()
        # collect parameters from the request and validate and save them to the DB
        parameters = piping.plugin.parameters.all()
        if piping.id in self.parsed_parameters:
            for parameter in parameters:
                if parameter.name in self.parsed_parameters[piping.id]:
                    requested_value = self.parsed_parameters[piping.id][parameter.name]
                    data = {'value': requested_value}
                else:
                    default = getattr(piping, parameter.type + '_param').get(
                        plugin_param=parameter)
                    data = {'value': default.value}
                parameter_serializer = PARAMETER_SERIALIZERS[parameter.type](
                    data=data)
                parameter_serializer.is_valid(raise_exception=True)
                parameter_serializer.save(plugin_inst=plugin_inst,
                                          plugin_param=parameter)
        else:
            for parameter in parameters:
                default = getattr(piping, parameter.type + '_param').get(
                    plugin_param=parameter)
                data = {'value': default.value}
                parameter_serializer = PARAMETER_SERIALIZERS[parameter.type](
                    data=data)
                parameter_serializer.is_valid(raise_exception=True)
                parameter_serializer.save(plugin_inst=plugin_inst,
                                          plugin_param=parameter)
        return plugin_inst


class PipelineInstanceListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of pipeline instances resulting from a query search.
    """
    serializer_class = PipelineInstanceSerializer
    queryset = PipelineInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PipelineInstanceFilter


class PipelineInstanceDetail(generics.RetrieveAPIView):
    """
    A pipeline instance view.
    """
    serializer_class = PipelineInstanceSerializer
    queryset = PipelineInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


class PipelineInstancePluginInstanceList(generics.ListAPIView):
    """
    A view for the collection of plugin instances that compose the pipeline instance.
    """
    serializer_class = PluginInstanceSerializer
    queryset = PipelineInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the plugin instances that are part of
        the queried pipeline instance.
        """
        queryset = self.get_plugin_instances_queryset()
        return services.get_list_response(self, queryset)

    def get_plugin_instances_queryset(self):
        """
        Custom method to get a queryset with all the plugin instances that are part of
        the queried pipeline instance.
        """
        pipeline_inst = self.get_object()
        return self.filter_queryset(pipeline_inst.plugin_instances)


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
        instance's parameters in the request are also properly saved to the DB. Finally
        the plugin's app is run with the provided plugin instance's parameters.
        """
        # get previous plugin instance and create the new plugin instance
        request_data = serializer.context['request'].data
        previous_id = request_data['previous_id'] if 'previous_id' in request_data else ""
        previous = serializer.validate_previous(previous_id)
        plugin = self.get_object()
        plugin_inst = serializer.save(owner=self.request.user, plugin=plugin,
                                      previous=previous,
                                      compute_resource=plugin.compute_resource)
        # collect parameters from the request and validate and save them to the DB
        parameters = plugin.parameters.all()
        parameters_dict = {}
        for parameter in parameters:
            if parameter.name in request_data:
                requested_value = request_data[parameter.name]
                data = {'value': requested_value}
                parameter_serializer = PARAMETER_SERIALIZERS[parameter.type](data=data)
                parameter_serializer.is_valid(raise_exception=True)
                parameter_serializer.save(plugin_inst=plugin_inst, plugin_param=parameter)
                parameters_dict[parameter.name] = requested_value
        # run the plugin's app
        PluginAppManager.run_plugin_app(plugin_inst,
                                  parameters_dict,
                                  service             = 'pfcon',
                                  inputDirOverride    = '/share/incoming',
                                  outputDirOverride   = '/share/outgoing')

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of instances for the queried plugin.
        A document-level link relation, query list and a collection+json template are
        also added to the response.
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
        template_data = {'title': "", 'previous_id': "", 'cpu_limit':"",
                         'memory_limit':"", 'number_of_workers':"", 'gpu_limit':""}
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
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PluginInstanceFilter

        
class PluginInstanceDetail(generics.RetrieveAPIView):
    """
    A plugin instance view.
    """
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overloaded method to check a plugin's instance status.
        """
        instance = self.get_object()
        PluginAppManager.check_plugin_app_exec_status(instance)
        response = super(PluginInstanceDetail, self).retrieve(request, *args, **kwargs)
        return response


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
        Custom method to get a queryset with all the parameters regardless their type.
        """
        instance = self.get_object()
        queryset = []
        queryset.extend(list(instance.path_param.all()))
        queryset.extend(list(instance.string_param.all()))
        queryset.extend(list(instance.integer_param.all()))
        queryset.extend(list(instance.float_param.all()))
        queryset.extend(list(instance.boolean_param.all()))
        return self.filter_queryset(queryset)


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
