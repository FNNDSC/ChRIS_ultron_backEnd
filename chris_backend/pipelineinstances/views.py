
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework.serializers import ValidationError

from collectionjson import services
from pipelines.models import Pipeline
from plugininstances.models import PluginInstance
from plugininstances.serializers import PluginInstanceSerializer
from plugininstances.serializers import PARAMETER_SERIALIZERS
from .models import PipelineInstance, PipelineInstanceFilter
from .serializers import PipelineInstanceSerializer


class PipelineInstanceList(generics.ListCreateAPIView):
    """
    A view for the collection of pipeline instances.
    """
    serializer_class = PipelineInstanceSerializer
    queryset = Pipeline.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Overriden to associate a pipeline with the newly created pipeline instance before
        first saving to the DB. All the pipeline instance's parameters in the request are
        parsed and properly saved to the DB with the corresponding plugin instances.
        """
        # get previous plugin instance
        request_data = serializer.context['request'].data
        previous_plugin_inst_id = request_data['previous_plugin_inst_id'] \
            if 'previous_plugin_inst_id' in request_data else ""
        previous_plugin_inst = serializer.validate_previous_plugin_inst(
            previous_plugin_inst_id)
        pipeline = self.get_object()
        # parse and transform plugin parameter names in the request
        self.parsed_parameters = serializer.parse_parameters()
        # create a plugin instance for each piping in the pipeline in the same
        # tree order as the pipings
        pipings_tree = pipeline.get_pipings_tree()
        tree = pipings_tree['tree']
        root_id = pipings_tree['root_id']
        root_pip = tree[root_id]['piping']
        plugin_inst_dict = self.create_plugin_inst(root_pip, previous_plugin_inst)
        plugin_instances = [plugin_inst_dict]
        # breath-first traversal
        plugin_inst_queue = [plugin_inst_dict]
        pip_id_queue = [root_id]
        while len(pip_id_queue):
            curr_id = pip_id_queue.pop(0)
            curr_plugin_inst_dict = plugin_inst_queue.pop(0)
            child_ids = tree[curr_id]['child_ids']
            for id in child_ids:
                pip = tree[id]['piping']
                plugin_inst_dict = self.create_plugin_inst(
                    pip, curr_plugin_inst_dict['plugin_inst'])
                plugin_instances.append(plugin_inst_dict)
                pip_id_queue.append(id)
                plugin_inst_queue.append(plugin_inst_dict)
        # if no validation errors at this point then save to the DB
        self.pipeline_inst = serializer.save(pipeline=pipeline)
        for plg_inst_dict in plugin_instances:
            self.save_plugin_inst(plg_inst_dict)

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
        Custom method to create a plugin instance and validate its parameters.
        """
        owner = self.request.user
        plugin_inst = PluginInstance()
        plugin_inst.owner = owner
        plugin_inst.plugin = piping.plugin
        plugin_inst.previous = previous_inst
        plugin_inst.compute_resource = piping.plugin.compute_resource
        # collect and validate parameters from the request
        parsed_parameters = self.parsed_parameters
        parameter_serializers = []
        parameters = piping.plugin.parameters.all()
        for parameter in parameters:
            if (piping.id in parsed_parameters) and (parameter.name in
                                                     parsed_parameters[piping.id]):
                request_value = parsed_parameters[piping.id][parameter.name]
                data = {'value': request_value}
            else:
                default = getattr(piping, parameter.type + '_param').filter(
                    plugin_param=parameter)[0]
                data = {'value': default.value}
            parameter_serializer = PARAMETER_SERIALIZERS[parameter.type](data=data)
            try:
                parameter_serializer.is_valid(raise_exception=True)
            except ValidationError:
                raise ValidationError({'detail': 'A valid %s is required for %s'
                                                 % (parameter.type, parameter.name)})
            parameter_serializers.append((parameter, parameter_serializer))
        return {'plugin_inst': plugin_inst,
                'parameter_serializers': parameter_serializers}

    def save_plugin_inst(self, plg_inst_dict):
        """
        Custom method to save a plugin instance and its parameters to the DB.
        """
        plg_inst = plg_inst_dict['plugin_inst']
        plg_inst.pipeline_inst = self.pipeline_inst
        previous = plg_inst.previous
        plg_inst.save()
        plg_inst.previous = previous
        plg_inst.save()
        for param, param_serializer in plg_inst_dict['parameter_serializers']:
            param_serializer.save(plugin_inst=plg_inst, plugin_param=param)


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
        return self.filter_queryset(pipeline_inst.plugin_instances.all())
