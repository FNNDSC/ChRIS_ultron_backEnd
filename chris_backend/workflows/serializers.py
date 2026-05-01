
import json
from typing import List, Optional

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from pipelines.serializers import (DEFAULT_PIPING_PARAMETER_SERIALIZERS,
                                    PluginPipingSerializer)
from plugininstances.models import PluginInstance
from ._types import GivenNodeInfo, PipingId, GivenWorkflowPluginParameterDefault
from .models import Workflow

RESOURCE_FIELDS = ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit')


class WorkflowSerializer(serializers.HyperlinkedModelSerializer):
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    pipeline_name = serializers.ReadOnlyField(source='pipeline.name')
    previous_plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True,
                                                       required=False)
    nodes_info = serializers.JSONField(write_only=True, default='[]')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    created_jobs = serializers.IntegerField(default=0, read_only=True)
    waiting_jobs = serializers.IntegerField(default=0, read_only=True)
    copying_jobs = serializers.IntegerField(default=0, read_only=True)
    scheduled_jobs = serializers.IntegerField(default=0, read_only=True)
    started_jobs = serializers.IntegerField(default=0, read_only=True)
    uploading_jobs = serializers.IntegerField(default=0, read_only=True)
    registering_jobs = serializers.IntegerField(default=0, read_only=True)
    finished_jobs = serializers.IntegerField(default=0, read_only=True)
    errored_jobs = serializers.IntegerField(default=0, read_only=True)
    cancelled_jobs = serializers.IntegerField(default=0, read_only=True)
    pipeline = serializers.HyperlinkedRelatedField(view_name='pipeline-detail',
                                                   read_only=True)
    plugin_instances = serializers.HyperlinkedIdentityField(
        view_name='workflow-plugininstance-list')

    class Meta:
        model = Workflow
        fields = ('url', 'id', 'creation_date', 'title', 'pipeline_id',
                  'pipeline_name', 'owner_username', 'previous_plugin_inst_id',
                  'created_jobs', 'waiting_jobs', 'copying_jobs', 'scheduled_jobs', 
                  'started_jobs', 'uploading_jobs', 'registering_jobs', 'finished_jobs', 
                  'errored_jobs', 'cancelled_jobs', 'nodes_info', 'pipeline', 
                  'plugin_instances')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance is not None: # on update
            self.fields['previous_plugin_inst_id'].read_only = True
            self.fields['nodes_info'].read_only = True

    def create(self, validated_data):
        """
        Overriden to delete 'previous_plugin_inst_id' and 'nodes_info' from serializer
        data as they are not model fields.
        """
        del validated_data['previous_plugin_inst_id']
        del validated_data['nodes_info']
        return super(WorkflowSerializer, self).create(validated_data)

    def validate_previous_plugin_inst_id(self, previous_plugin_inst_id) -> PluginInstance:
        """
        Overriden to check that the provided previous plugin instance id exists in the
        DB and that the user can run plugins within the corresponding feed.
        """
        try:
            pk = int(previous_plugin_inst_id)
            previous_plugin_inst = PluginInstance.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            raise serializers.ValidationError(
                [f"Couldn't find any 'previous' plugin instance with id "
                 f"{previous_plugin_inst_id}."])

        # check that the user can run plugins within this feed
        user = self.context['request'].user
        feed = previous_plugin_inst.feed

        if not (user == feed.owner or feed.has_user_permission(user)):
            raise serializers.ValidationError([f'Not allowed to write to feed for '
                                               f'previous instance with id {pk}.'])
        return previous_plugin_inst

    def validate_nodes_info(self, nodes_info: Optional[str]) -> List[GivenNodeInfo]:
        """
        Overriden to validate the runtime data for the workflow. It should be an optional
        JSON string encoding a list of dictionaries. Each dictionary is a workflow node
        containing a plugin piping_id, and optionally: compute_resource_name, title,
        and/or a list of dictionaries called plugin_parameter_defaults.

        Returned data is made canonical: dictionaries are created for unmentioned pipings,
        and undefined keys are initialized with ``None``.
        """
        if self.instance:  # this validation only happens on create and not on update
            return []

        input_node_list = self._parse_nodes_info_json(nodes_info)

        pipeline = self.context['view'].get_object()
        node_list: List[GivenNodeInfo] = []
        titles: set = set()

        for piping in pipeline.plugin_pipings.all():
            raw = next(
                (d for d in input_node_list if d.get('piping_id') == piping.id), None)
            
            d = self._build_canonical_node(piping, raw, titles)

            self._validate_compute_resource(piping, d.get('compute_resource_name'))

            self._validate_piping_param_defaults(
                piping, d.get('plugin_parameter_defaults'))
            
            node_list.append(d)
        return node_list

    @staticmethod
    def _parse_nodes_info_json(nodes_info: Optional[str]) -> list:
        """
        Custom internal method to decode the ``nodes_info`` JSON payload, ensuring it 
        is a list whose elements all carry a ``piping_id``. Defaults a ``None`` payload 
        to an empty list to match the legacy behavior.
        """
        if nodes_info is None:
            nodes_info = '[]'

        try:
            input_node_list = json.loads(nodes_info)
        except json.decoder.JSONDecodeError:
            # overriden validation methods automatically add the field name to the msg
            raise serializers.ValidationError([f'Invalid JSON string {nodes_info}.'])
        
        if not isinstance(input_node_list, list):
            raise serializers.ValidationError([f'Invalid list in {nodes_info}'])
        
        for d in input_node_list:
            if 'piping_id' not in d:
                raise serializers.ValidationError(
                    f'Element does not specify "piping_id": {d}')
        return input_node_list

    def _build_canonical_node(self, piping, raw_node: Optional[dict],
                              titles: set) -> GivenNodeInfo:
        """
        Custom internal method to return a canonical :class:`GivenNodeInfo` for 
        ``piping``. If ``raw_node`` is ``None`` (the user did not mention this piping) 
        a fully-defaulted dict is built. Otherwise the raw dict is mutated in place to 
        fill missing keys with ``None``/``[]`` and the supplied resource overrides are 
        validated. 
        ``titles`` is mutated to include the resolved title; raises if the title was 
        already used by an earlier piping in the same workflow tree.
        """
        if raw_node is None:
            self._register_title(piping.title, titles)
            return GivenNodeInfo(
                piping_id=piping.id,
                compute_resource_name=None,
                title=piping.title,
                plugin_parameter_defaults=[],
                cpu_limit=None,
                memory_limit=None,
                number_of_workers=None,
                gpu_limit=None,
            )

        # collect the user-supplied piping fields for validation before
        # the canonical-form normalization below mutates the dict
        piping_data = {f: raw_node[f]
                       for f in ('title', *RESOURCE_FIELDS) if f in raw_node}
        
        if 'title' not in raw_node:
            raw_node['title'] = piping.title

        self._register_title(raw_node['title'], titles)

        raw_node.setdefault('compute_resource_name', None)
        raw_node.setdefault('plugin_parameter_defaults', [])

        for f in RESOURCE_FIELDS:
            raw_node.setdefault(f, None)

        self.validate_piping_overrides(piping, piping_data)
        return raw_node

    @staticmethod
    def _register_title(title: str, titles: set) -> None:
        """Track ``title`` as used; raise if it was already taken in this workflow."""
        if title in titles:
            raise serializers.ValidationError(
                [f"Workflow tree can not contain duplicated title: {title}"])
        titles.add(title)

    @staticmethod
    def _validate_compute_resource(piping, cr_name) -> None:
        """Raise if ``cr_name`` is set but not registered for the piping's plugin."""
        if cr_name and piping.plugin.compute_resources.filter(
                name=cr_name).count() == 0:
            raise serializers.ValidationError(
                [f'Plugin for pipping with id {piping.id} has not been registered '
                 f'with a compute resource named {cr_name}'])

    def _validate_piping_param_defaults(
            self, piping,
            piping_param_defaults: List[GivenWorkflowPluginParameterDefault]) -> None:
        """
        Run :meth:`validate_piping_params` for every default-parameter row attached
        to ``piping`` (across the four type-specific default tables).
        """
        param_sets = (piping.string_param, piping.integer_param,
                      piping.float_param, piping.boolean_param)
        
        for param_set in param_sets:
            for default_param in param_set.all():
                self.validate_piping_params(
                    piping.id, default_param, piping_param_defaults)

    @staticmethod
    def validate_piping_overrides(piping, piping_data):
        """
        Helper method to validate the per-piping title and resource overrides
        (cpu_limit, memory_limit, number_of_workers, gpu_limit) supplied for a
        workflow node. Delegates to PluginPipingSerializer so the same
        format-parsing and min/max range semantics used when building a pipeline
        also apply here.
        """
        if not piping_data:
            return
        
        piping_serializer = PluginPipingSerializer(
            data=piping_data, partial=True, context={'plugin': piping.plugin})
        
        try:
            piping_serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            raise serializers.ValidationError(
                [f"Invalid data for piping with id {piping.id}: {e.detail}"])

    @staticmethod
    def validate_piping_params(piping_id: PipingId, default_param, piping_param_defaults: List[GivenWorkflowPluginParameterDefault]):
        """
        Helper method to validate that if a default value doesn't exist in the
        corresponding pipeline for a piping parameter then a default is provided for it
        when creating a new runtime workflow.
        """
        matching = [d for d in piping_param_defaults if
                    d.get('name') == default_param.plugin_param.name]
        
        if default_param.value is None and (
                not matching or matching[0].get('default') is None):
            raise serializers.ValidationError(
                [f"Can not run workflow. Parameter "
                 f"'{default_param.plugin_param.name}' for piping with id "
                 f"{piping_id} does not have a default value in the pipeline"])
        
        if matching:
            WorkflowSerializer._validate_supplied_param_default(
                piping_id, default_param, matching[0].get('default'))

    @staticmethod
    def _validate_supplied_param_default(piping_id: PipingId, default_param,
                                         supplied) -> None:
        """
        Validate a user-supplied default value for ``default_param``: must be
        non-null and parse cleanly via the type-specific default serializer.
        """
        if supplied is None:
            raise serializers.ValidationError(
                f"\"default\" not provided for parameter "
                f"\"{default_param.plugin_param.name}\" of piping_id={piping_id}")
        
        param_type = default_param.plugin_param.type
        default_serializer_cls = DEFAULT_PIPING_PARAMETER_SERIALIZERS[param_type]
        default_serializer = default_serializer_cls(data={'value': supplied})

        try:
            default_serializer.is_valid(raise_exception=True)
        except Exception:
            raise serializers.ValidationError(
                [f'Invalid parameter default value {supplied} for '
                 f"parameter '{default_param.plugin_param.name}' and pipping "
                 f'with id {piping_id}'])

    def validate(self, data):
        """
        Overriden to validate that a previous plugin instance id was passed in the
        create request.
        """
        if not self.instance:  # this validation only happens on create and not on update
            if 'previous_plugin_inst_id' not in data:
                raise serializers.ValidationError(
                    {'previous_plugin_inst_id': ["This field is required."]})
        return data
