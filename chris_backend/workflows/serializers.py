
import json
from typing import List, Optional

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from pipelines.serializers import DEFAULT_PIPING_PARAMETER_SERIALIZERS
from plugininstances.models import PluginInstance
from plugininstances.serializers import PluginInstanceSerializer
from ._types import GivenNodeInfo, PipingId, GivenWorkflowPluginParameterDefault
from .models import Workflow


class WorkflowSerializer(serializers.HyperlinkedModelSerializer):
    created_plugin_inst_ids = serializers.ReadOnlyField()
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    pipeline_name = serializers.ReadOnlyField(source='pipeline.name')
    previous_plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True)
    nodes_info = serializers.JSONField(write_only=True, default='[]')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    pipeline = serializers.HyperlinkedRelatedField(view_name='pipeline-detail',
                                                   read_only=True)

    class Meta:
        model = Workflow
        fields = ('url', 'id', 'creation_date', 'created_plugin_inst_ids', 'pipeline_id',
                  'pipeline_name', 'owner_username', 'previous_plugin_inst_id',
                  'nodes_info', 'pipeline')

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
        Overriden to check that an integer id is provided for previous plugin instance.
        Then check that the id exists in the DB and that the user can run plugins
        within the corresponding feed.
        """
        if not previous_plugin_inst_id:
            raise serializers.ValidationError(['This field is required.'])
        try:
            pk = int(previous_plugin_inst_id)
            previous_plugin_inst = PluginInstance.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            raise serializers.ValidationError(
                [f"Couldn't find any 'previous' plugin instance with id "
                 f"{previous_plugin_inst_id}."])
        # check that the user can run plugins within this feed
        user = self.context['request'].user
        if user not in previous_plugin_inst.feed.owner.all():
            raise serializers.ValidationError([f'User is not an owner of feed for '
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
        if nodes_info is None:
            nodes_info = '[]'
        try:
            node_list: List[GivenNodeInfo] = json.loads(nodes_info)
        except json.decoder.JSONDecodeError:
            # overriden validation methods automatically add the field name to the msg
            raise serializers.ValidationError([f'Invalid JSON string {nodes_info}.'])
        if not isinstance(node_list, list):
            raise serializers.ValidationError([f'Invalid list in {nodes_info}'])

        for d in node_list:
            if 'piping_id' not in d:
                raise serializers.ValidationError(
                    f'Element does not specify "piping_id": {d}')

        pipeline = self.context['view'].get_object()
        pipings = list(pipeline.plugin_pipings.all())

        for piping in pipings:
            d_l = [d for d in node_list if d.get('piping_id') == piping.id]
            if d_l:
                d = d_l[0]
                if 'title' in d:
                    title = d['title']
                    plg_inst_serializer = PluginInstanceSerializer(data={'title': title})
                    try:
                        plg_inst_serializer.is_valid(raise_exception=True)
                    except Exception:
                        msg = [f'Invalid title {title} for pipping with id {piping.id}']
                        raise serializers.ValidationError(msg)
                else:
                    d['title'] = piping.title
                if 'compute_resource_name' not in d:
                    d['compute_resource_name'] = None
                if 'plugin_parameter_defaults' not in d:
                    d['plugin_parameter_defaults'] = []
            else:
                d = GivenNodeInfo(
                    piping_id=piping.id,
                    compute_resource_name=None,
                    title=piping.title,
                    plugin_parameter_defaults=[]
                )
                node_list.append(d)

            cr_name = d.get('compute_resource_name')
            if cr_name and piping.plugin.compute_resources.filter(name=cr_name).count() == 0:
                msg = [f'Plugin for pipping with id {piping.id} has not been registered '
                       f'with a compute resource named {cr_name}']
                raise serializers.ValidationError(msg)

            piping_param_defaults = d.get('plugin_parameter_defaults')
            param_sets = (piping.string_param, piping.integer_param, piping.float_param, piping.boolean_param)
            for param_set in param_sets:
                for default_param in param_set.all():
                    self.validate_piping_params(piping.id, default_param, piping_param_defaults)
        return node_list

    @staticmethod
    def validate_piping_params(piping_id: PipingId, default_param, piping_param_defaults: List[GivenWorkflowPluginParameterDefault]):
        """
        Helper method to validate that if a default value doesn't exist in the
        corresponding pipeline for a piping parameter then a default is provided for it
        when creating a new runtime workflow.
        """
        l = [d for d in piping_param_defaults if
             d.get('name') == default_param.plugin_param.name]
        if default_param.value is None and (not l or l[0].get('default') is None):
            raise serializers.ValidationError(
                [f"Can not run workflow. Parameter "
                 f"'{default_param.plugin_param.name}' for piping with id "
                 f"{piping_id} does not have a default value in the pipeline"])
        if l:
            param_default = l[0].get('default')
            if not param_default:
                raise serializers.ValidationError(
                    f"\"default\" not provided for parameter \"{default_param.plugin_param.name}\" "
                    f"of piping_id={piping_id}"
                )
            param_type = default_param.plugin_param.type
            default_serializer_cls = DEFAULT_PIPING_PARAMETER_SERIALIZERS[param_type]
            default_serializer = default_serializer_cls(data={'value': param_default})
            try:
                default_serializer.is_valid(raise_exception=True)
            except Exception:
                msg = [f'Invalid parameter default value {param_default} for '
                       f"parameter '{default_param.plugin_param.name}' and pipping "
                       f'with id {piping_id}']
                raise serializers.ValidationError(msg)
