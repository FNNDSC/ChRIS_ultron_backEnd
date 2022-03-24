
import json

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from plugininstances.models import PluginInstance
from plugininstances.serializers import PluginInstanceSerializer
from pipelines.serializers import DEFAULT_PIPING_PARAMETER_SERIALIZERS

from .models import Workflow


class WorkflowSerializer(serializers.HyperlinkedModelSerializer):
    created_plugin_inst_ids = serializers.ReadOnlyField()
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    pipeline_name = serializers.ReadOnlyField(source='pipeline.name')
    previous_plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True)
    nodes_info = serializers.JSONField(write_only=True)
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

    def validate_previous_plugin_inst_id(self, previous_plugin_inst_id):
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

    def validate_nodes_info(self, nodes_info):
        """
        Overriden to validate the runtime data for the workflow. It should be a
        JSON string encoding a list of dictionaries. Each dictionary is a workflow node
        containing a plugin piping_id, compute_resource_name, title and a list of
        dictionaries called plugin_parameter_defaults. Each dictionary in this list has
        name and default keys.
        """
        try:
            node_list = list(json.loads(nodes_info))
        except json.decoder.JSONDecodeError:
            # overriden validation methods automatically add the field name to the msg
            raise serializers.ValidationError([f'Invalid JSON string {nodes_info}.'])
        except Exception:
            raise serializers.ValidationError([f'Invalid list in {nodes_info}'])

        pipeline = self.context['view'].get_object()
        pipings = list(pipeline.plugin_pipings.all())
        if len(node_list) != len(pipings):
            raise serializers.ValidationError(
                [f'Invalid length for list in {nodes_info}'])

        for piping in pipings:
            d_l = [d for d in node_list if d.get('piping_id') == piping.id]
            try:
                d = d_l[0]
            except IndexError:
                raise serializers.ValidationError([f'Missing data for plugin pipping '
                                                   f'with id {piping.id}'])
            cr_name = d.get('compute_resource_name')
            if not cr_name:
                raise serializers.ValidationError([f'Missing compute_resource_name key in'
                                                   f' {d}'])
            if piping.plugin.compute_resources.filter(name=cr_name).count() == 0:
                msg = [f'Plugin for pipping with id {piping.id} has not been registered '
                       f'with a compute resource named {cr_name}']
                raise serializers.ValidationError(msg)

            title = d.get('title', '')
            plg_inst_serializer = PluginInstanceSerializer(data={'title': title})
            try:
                plg_inst_serializer.is_valid(raise_exception=True)
            except Exception:
                msg = [f'Invalid title {title} for pipping with id {piping.id}']
                raise serializers.ValidationError(msg)

            piping_param_defaults = d.get('plugin_parameter_defaults', [])
            self.validate_piping_params(piping.id, piping.string_param.all(),
                                        piping_param_defaults)
            self.validate_piping_params(piping.id, piping.integer_param.all(),
                                        piping_param_defaults)
            self.validate_piping_params(piping.id, piping.float_param.all(),
                                        piping_param_defaults)
            self.validate_piping_params(piping.id, piping.boolean_param.all(),
                                        piping_param_defaults)
        return node_list

    @staticmethod
    def validate_piping_params(piping_id, piping_default_params, piping_param_defaults):
        """
        Helper method to validate that if a default value doesn't exist in the
        corresponding pipeline for a piping parameter then a default is provided for it
        when creating a new runtime workflow.
        """
        for default_param in piping_default_params:
            l = [d for d in piping_param_defaults if
                 d.get('name') == default_param.plugin_param.name]
            if default_param.value is None and (not l or l[0].get('default') is None):
                raise serializers.ValidationError(
                    [f"Can not run workflow. Parameter "
                     f"'{default_param.plugin_param.name}' for piping with id "
                     f"{piping_id} does not have a default value in the pipeline"])
            if l and l[0].get('default'):
                param_default = l[0].get('default')
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
