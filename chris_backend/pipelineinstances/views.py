
from rest_framework import generics, permissions
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from collectionjson import services
from pipelines.models import Pipeline
from plugininstances.models import PluginInstance
from plugininstances.serializers import PluginInstanceSerializer
from plugininstances.serializers import PARAMETER_SERIALIZERS
from plugininstances.tasks import cancel_plugin_instance
from plugins.fields import MemoryInt, CPUInt

from .models import PipelineInstance, PipelineInstanceFilter
from .serializers import PipelineInstanceSerializer
from .permissions import IsOwnerOrChrisOrReadOnly


class PipelineInstanceList(generics.ListCreateAPIView):
    """
    A view for the collection of pipeline-specific instances.
    """
    http_method_names = ['get', 'post']
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
        self.pipeline_inst = serializer.save(owner=self.request.user, pipeline=pipeline)
        for plg_inst_dict in plugin_instances:
            self.save_plugin_inst(plg_inst_dict)

        # run the plugin's app
        # PipelineInstanceManager.run_pipeline_instance(pipeline_inst,
        #                                 parameters_dict,
        #                                 service='pfcon',
        #                                 inputDirOverride='/share/incoming',
        #                                 outputDirOverride='/share/outgoing')

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of pipeline instances for the queried pipeline.
        A document-level link relation and a collection+json template are also added to
        the response.
        """
        queryset = self.get_pipeline_instances_queryset()
        response = services.get_list_response(self, queryset)
        pipeline = self.get_object()
        # append document-level link relations
        links = {'pipeline': reverse('pipeline-detail', request=request,
                                   kwargs={"pk": pipeline.id})}
        response = services.append_collection_links(response, links)
        # append write template
        template_data = {'previous_plugin_inst_id': "", 'title': "", 'description': "",
                         'cpu_limit': "", 'memory_limit': "", 'number_of_workers': "",
                         'gpu_limit': ""}
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
        plugin_inst.compute_resource = piping.plugin.compute_resources.all()[0]
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
        plg = plg_inst.plugin
        pipeline_inst = self.pipeline_inst
        plg_inst.pipeline_inst = pipeline_inst
        plg_inst.title = pipeline_inst.title
        # set cpu limit
        if pipeline_inst.cpu_limit:
            plg_inst.cpu_limit = pipeline_inst.cpu_limit
            if plg_inst.cpu_limit < CPUInt(plg.min_cpu_limit):
                plg_inst.cpu_limit = CPUInt(plg.min_cpu_limit)
            if plg_inst.cpu_limit > CPUInt(plg.max_cpu_limit):
                plg_inst.cpu_limit = CPUInt(plg.max_cpu_limit)
        # set memory limit
        if pipeline_inst.memory_limit:
            plg_inst.memory_limit = pipeline_inst.memory_limit
            if plg_inst.memory_limit < MemoryInt(plg.min_memory_limit):
                plg_inst.memory_limit = MemoryInt(plg.min_memory_limit)
            if plg_inst.memory_limit > MemoryInt(plg.max_memory_limit):
                plg_inst.memory_limit = MemoryInt(plg.max_memory_limit)
        # set number of workers
        if pipeline_inst.number_of_workers:
            plg_inst.number_of_workers = pipeline_inst.number_of_workers
            if plg_inst.number_of_workers < plg.number_of_workers:
                plg_inst.number_of_workers = plg.min_number_of_workers
            if plg_inst.number_of_workers > plg.max_number_of_workers:
                plg_inst.number_of_workers = plg.max_number_of_workers
        # set gpu limit
        if pipeline_inst.gpu_limit:
            plg_inst.gpu_limit = pipeline_inst.gpu_limit
            if plg_inst.gpu_limit < plg.min_gpu_limit:
                plg_inst.gpu_limit = plg.min_gpu_limit
            if plg_inst.gpu_limit > plg.max_gpu_limit:
                plg_inst.gpu_limit = plg.max_gpu_limit
        # save plugin instance
        previous = plg_inst.previous
        plg_inst.save()
        plg_inst.previous = previous
        plg_inst.save()
        # save plugin instance's parameters
        for param, param_serializer in plg_inst_dict['parameter_serializers']:
            param_serializer.save(plugin_inst=plg_inst, plugin_param=param)


class AllPipelineInstanceList(generics.ListAPIView):
    """
    A view for the collection of all pipeline instances.
    """
    http_method_names = ['get']
    serializer_class = PipelineInstanceSerializer
    queryset = PipelineInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to add a query list and document-level link relation to the response.
        """
        response = super(AllPipelineInstanceList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('allpipelineinstance-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'pipelines': reverse('pipeline-list', request=request)}
        return services.append_collection_links(response, links)


class AllPipelineInstanceListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of pipeline instances resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = PipelineInstanceSerializer
    queryset = PipelineInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PipelineInstanceFilter


class PipelineInstanceDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A pipeline instance view.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = PipelineInstanceSerializer
    queryset = PipelineInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template to the response.
        """
        response = super(PipelineInstanceDetail, self).retrieve(request, *args, **kwargs)
        template_data = {'title': '', 'description': ''}
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
        return super(PipelineInstanceDetail, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Overriden to cancel all the associated plugin instances before attempting to
        delete the pipeline instance.
        """
        pipeline_inst = self.get_object()
        for plg_inst in pipeline_inst.plugin_instances.all():
            if plg_inst.status == 'started':
                cancel_plugin_instance.delay(plg_inst.id)  # call async task
            plg_inst.status = 'cancelled'
            plg_inst.save()
        return super(PipelineInstanceDetail, self).destroy(request, *args, **kwargs)


class PipelineInstancePluginInstanceList(generics.ListAPIView):
    """
    A view for the collection of plugin instances that compose the pipeline instance.
    """
    http_method_names = ['get']
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
