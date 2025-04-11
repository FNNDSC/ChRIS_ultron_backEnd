
from typing import List, Dict
from collections import deque

from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from drf_spectacular.utils import extend_schema, extend_schema_view

from collectionjson import services
from pipelines.models import Pipeline
from plugininstances.models import PluginInstance, PARAMETER_MODELS
from plugininstances.serializers import PluginInstanceSerializer
from plugininstances.utils import run_if_ready
from plugininstances.tasks import cancel_plugin_instance
from ._types import (GivenNodeInfo, WorkflowPluginInstanceTemplateFactory,
                     WorkflowPluginInstanceTemplate, PipingId)
from .models import Workflow, WorkflowFilter
from .permissions import IsOwnerOrChrisOrReadOnly
from .serializers import WorkflowSerializer

@extend_schema_view(
    get=extend_schema(operation_id="workflows_list")
)
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
        first saving to the DB. All the workflow's parameters in the request are
        parsed and properly saved to the DB with the corresponding plugin instances.
        """
        previous_plugin_inst = serializer.validated_data['previous_plugin_inst_id']
        nodes_info: List[GivenNodeInfo] = serializer.validated_data['nodes_info']
        pipeline = self.get_object()
        title = serializer.validated_data.get('title')
        if title is None:
            title = pipeline.name  # set default value
        workflow = serializer.save(owner=self.request.user, pipeline=pipeline,
                                   title=title)

        pipings_tree = pipeline.get_pipings_tree()
        tree = pipings_tree['tree']
        factory = WorkflowPluginInstanceTemplateFactory(tree=tree)

        inst_data: Dict[PipingId, WorkflowPluginInstanceTemplate] = {
            info['piping_id']: factory.inflate(info)
            for info in nodes_info
        }

        root_id = pipings_tree['root_id']
        plugin_inst = self.create_plugin_inst(inst_data[root_id], previous_plugin_inst,
                                              workflow)

        plugin_instances_dict = {root_id: plugin_inst}  # map from pip id to plg inst id

        # breath-first traversal
        plugin_inst_queue = deque()
        plugin_inst_queue.append(plugin_inst)
        pip_id_queue = deque()
        pip_id_queue.append(root_id)
        while len(pip_id_queue):
            curr_id = pip_id_queue.popleft()
            curr_plugin_inst = plugin_inst_queue.popleft()
            child_ids = tree[curr_id]['child_ids']
            for id in child_ids:
                plugin_inst = self.create_plugin_inst(inst_data[id], curr_plugin_inst,
                                                      workflow)
                plugin_instances_dict[id] = plugin_inst
                pip_id_queue.append(id)
                plugin_inst_queue.append(plugin_inst)

        # update 'plugininstances' param with parent plg inst ids for any 'ts' plg inst
        for plg_inst in plugin_instances_dict.values():
            if plg_inst.plugin.meta.type == 'ts':
                param = plg_inst.string_param.filter(
                    plugin_param__name='plugininstances').first()
                if param and param.value:
                    parent_pip_ids = [int(pip_id) for pip_id in param.value.split(',')]
                    parent_plg_inst_ids = [str(plugin_instances_dict[pip_id].id) for
                                           pip_id in parent_pip_ids]
                    param.value = ','.join(parent_plg_inst_ids)
                    param.save()

            # run plugin instance
            run_if_ready(plg_inst, plg_inst.previous)

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
        template_data = {'previous_plugin_inst_id': '', 'title': '', 'nodes_info': ''}
        return services.append_collection_template(response, template_data)

    def get_workflows_queryset(self):
        """
        Custom method to get the actual workflows' queryset.
        """
        pipeline = self.get_object()
        return self.filter_queryset(pipeline.workflows.all())

    def create_plugin_inst(self, data: WorkflowPluginInstanceTemplate, previous:
    PluginInstance, workflow: Workflow) -> PluginInstance:
        """
        Custom method to create a plugin instance and set its parameters.
        """
        plg_inst = PluginInstance.objects.create(
            plugin=data.piping.plugin,
            owner=self.request.user,
            previous=previous,
            title=data.title,
            compute_resource=data.compute_resource,
            workflow=workflow
        )
        for plugin_param, value in data.params:
            PARAMETER_MODELS[plugin_param.type].objects.create(
                plugin_inst=plg_inst,
                plugin_param=plugin_param,
                value=value
            )
        return plg_inst


@extend_schema_view(
    get=extend_schema(operation_id="all_workflows_list")
)
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


class WorkflowDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A workflow view.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = WorkflowSerializer
    queryset = Workflow.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template to the response.
        """
        response = super(WorkflowDetail, self).retrieve(request, *args, **kwargs)
        template_data = {'title': ''}
        return services.append_collection_template(response, template_data)

    def destroy(self, request, *args, **kwargs):
        """
        Overriden to cancel all the associated plugin instances before attempting to
        delete the workflow.
        """
        workflow = self.get_object()
        for plg_inst in workflow.plugin_instances.all():
            if plg_inst.status == 'started':
                cancel_plugin_instance.delay(plg_inst.id)  # call async task
            plg_inst.status = 'cancelled'
            plg_inst.save()
        return super(WorkflowDetail, self).destroy(request, *args, **kwargs)


class WorkflowPluginInstanceList(generics.ListAPIView):
    """
    A view for the collection of plugin instances that compose the workflow.
    """
    http_method_names = ['get']
    serializer_class = PluginInstanceSerializer
    queryset = Workflow.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the plugin instances that are part of
        the queried workflow.
        """
        queryset = self.get_plugin_instances_queryset()
        return services.get_list_response(self, queryset)

    def get_plugin_instances_queryset(self):
        """
        Custom method to get a queryset with all the plugin instances that are part of
        the queried workflow.
        """
        workflow = self.get_object()
        return self.filter_queryset(workflow.plugin_instances.all())
