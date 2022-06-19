from typing import List, Dict

from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services
from pipelines.models import Pipeline
from plugininstances.models import PluginInstance, PARAMETER_MODELS
from plugininstances.utils import run_if_ready
from ._types import GivenNodeInfo, WorkflowPluginInstanceTemplateFactory, \
    WorkflowPluginInstanceTemplate, PipingId
from .models import Workflow, WorkflowFilter
from .permissions import IsOwnerOrChrisOrReadOnly
from .serializers import WorkflowSerializer


class WorkflowList(generics.ListCreateAPIView):
    """
    A view for the collection of pipeline-specific workflows.
    """
    http_method_names = ['get', 'post']
    serializer_class = WorkflowSerializer
    queryset = Pipeline.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Overriden to associate a pipeline with the newly created workflow before
        first saving to the DB. All the pipeline instance's parameters in the request are
        parsed and properly saved to the DB with the corresponding plugin instances.
        """
        previous_plugin_inst = serializer.validated_data['previous_plugin_inst_id']
        nodes_info: List[GivenNodeInfo] = serializer.validated_data['nodes_info']
        pipeline = self.get_object()
        pipings_tree = pipeline.get_pipings_tree()
        tree = pipings_tree['tree']
        factory = WorkflowPluginInstanceTemplateFactory(tree=tree)

        inst_data: Dict[PipingId, WorkflowPluginInstanceTemplate] = {
            info['piping_id']: factory.inflate(info)
            for info in nodes_info
        }

        root_id = pipings_tree['root_id']
        plugin_inst = self.create_plugin_inst(inst_data[root_id], previous_plugin_inst)
        plugin_instances = [plugin_inst]
        # breath-first traversal
        plugin_inst_queue = [plugin_inst]
        pip_id_queue = [root_id]
        while len(pip_id_queue):
            curr_id = pip_id_queue.pop(0)
            curr_plugin_inst = plugin_inst_queue.pop(0)
            child_ids = tree[curr_id]['child_ids']
            for id in child_ids:
                plugin_inst = self.create_plugin_inst(inst_data[id], curr_plugin_inst)
                plugin_instances.append(plugin_inst)
                pip_id_queue.append(id)
                plugin_inst_queue.append(plugin_inst)

        # save workflow to the DB
        created_plg_inst_ids = []
        for plg_inst in plugin_instances:
            created_plg_inst_ids.append(str(plg_inst.id))
        serializer.save(owner=self.request.user, pipeline=pipeline,
                        created_plugin_inst_ids=','.join(created_plg_inst_ids))

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of workflows for the queried pipeline.
        A document-level link relation and a collection+json template are also added to
        the response.
        """
        queryset = self.get_workflows_queryset()
        response = services.get_list_response(self, queryset)
        pipeline = self.get_object()
        # append document-level link relations
        links = {'pipeline': reverse('pipeline-detail', request=request,
                                   kwargs={"pk": pipeline.id})}
        response = services.append_collection_links(response, links)
        # append write template
        template_data = {'previous_plugin_inst_id': '', 'nodes_info': ''}
        return services.append_collection_template(response, template_data)

    def get_workflows_queryset(self):
        """
        Custom method to get the actual workflows' queryset.
        """
        pipeline = self.get_object()
        return self.filter_queryset(pipeline.workflows.all())

    def create_plugin_inst(self, data: WorkflowPluginInstanceTemplate, previous: PluginInstance) -> PluginInstance:
        """
        Custom method to create a plugin instance, set its parameters, and run it.
        """
        plg_inst = PluginInstance.objects.create(
            plugin=data.piping.plugin,
            owner=self.request.user,
            previous=previous,
            title=data.title,
            compute_resource=data.compute_resource
        )
        for plugin_param, value in data.params:
            PARAMETER_MODELS[plugin_param.type].objects.create(
                plugin_inst=plg_inst,
                plugin_param=plugin_param,
                value=value
            )
        run_if_ready(plg_inst, previous)
        return plg_inst


class AllWorkflowList(generics.ListAPIView):
    """
    A view for the collection of all workflows.
    """
    http_method_names = ['get']
    serializer_class = WorkflowSerializer
    queryset = Workflow.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to add a query list and document-level link relation to the response.
        """
        response = super(AllWorkflowList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('allworkflow-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'pipelines': reverse('pipeline-list', request=request)}
        return services.append_collection_links(response, links)


class AllWorkflowListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of workflows resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = WorkflowSerializer
    queryset = Workflow.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = WorkflowFilter


class WorkflowDetail(generics.RetrieveDestroyAPIView):
    """
    A workflow view.
    """
    http_method_names = ['get', 'delete']
    serializer_class = WorkflowSerializer
    queryset = Workflow.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrReadOnly,)
