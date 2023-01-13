
import json
from typing import List, Optional

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from pipelines.serializers import DEFAULT_PIPING_PARAMETER_SERIALIZERS
from plugininstances.models import PluginInstance
from plugininstances.serializers import PluginInstanceSerializer
from plugininstances.models import STATUS_CHOICES
from ._types import GivenNodeInfo, PipingId, GivenWorkflowPluginParameterDefault
from .models import Workflow


class WorkflowSerializer(serializers.HyperlinkedModelSerializer):
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    pipeline_name = serializers.ReadOnlyField(source='pipeline.name')
    previous_plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True,
                                                       required=False)
    nodes_info = serializers.JSONField(write_only=True, default='[]')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    created_jobs = serializers.SerializerMethodField()
    waiting_jobs = serializers.SerializerMethodField()
    scheduled_jobs = serializers.SerializerMethodField()
    started_jobs = serializers.SerializerMethodField()
    registering_jobs = serializers.SerializerMethodField()
    finished_jobs = serializers.SerializerMethodField()
    errored_jobs = serializers.SerializerMethodField()
    cancelled_jobs = serializers.SerializerMethodField()
    pipeline = serializers.HyperlinkedRelatedField(view_name='pipeline-detail',
                                                   read_only=True)
    plugin_instances = serializers.HyperlinkedIdentityField(
        view_name='workflow-plugininstance-list')

    class Meta:
        model = Workflow
        fields = ('url', 'id', 'creation_date', 'title', 'pipeline_id',
                  'pipeline_name', 'owner_username', 'previous_plugin_inst_id',
                  'created_jobs', 'waiting_jobs', 'scheduled_jobs', 'started_jobs',
                  'registering_jobs', 'finished_jobs', 'errored_jobs', 'cancelled_jobs',
                  'nodes_info', 'pipeline', 'plugin_instances')

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
        if self.instance:  # this validation only happens on create and not on update
            return []

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

        titles = []
        for piping in pipings:
            d_l = [d for d in node_list if d.get('piping_id') == piping.id]
            if d_l:
                d = d_l[0]
                if 'title' in d:
                    title = d['title']
                    if title in titles:
                        raise serializers.ValidationError(
                            [f"Workflow tree can not contain duplicated title: {title}"])
                    titles.append(title)
                    plg_inst_serializer = PluginInstanceSerializer(data={'title': title})
                    try:
                        plg_inst_serializer.is_valid(raise_exception=True)
                    except Exception:
                        msg = [f'Invalid title {title} for pipping with id {piping.id}']
                        raise serializers.ValidationError(msg)
                else:
                    title = piping.title
                    if title in titles:
                        raise serializers.ValidationError(
                            [f"Workflow tree can not contain duplicated title: {title}"])
                    titles.append(title)
                    d['title'] = title
                if 'compute_resource_name' not in d:
                    d['compute_resource_name'] = None
                if 'plugin_parameter_defaults' not in d:
                    d['plugin_parameter_defaults'] = []
            else:
                title = piping.title
                if title in titles:
                    raise serializers.ValidationError(
                        [f"Workflow tree can not contain duplicated title: {title}"])
                titles.append(title)
                d = GivenNodeInfo(
                    piping_id=piping.id,
                    compute_resource_name=None,
                    title=title,
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
            if param_default is None:
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

    def validate(self, data):
        """
        Overriden to validate that a previous plugin instance id was passsed in the
        create request.
        """
        if not self.instance:  # this validation only happens on create and not on update
            if 'previous_plugin_inst_id' not in data:
                raise serializers.ValidationError(
                    {'previous_plugin_inst_id': ["This field is required."]})
        return data

    def get_created_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'created' status.
        """
        if 'created' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: 'created'.")
        return obj.get_plugin_instances_status_count('created')

    def get_waiting_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'waiting' status.
        """
        if 'waiting' not in [status[0] for status in STATUS_CHOICES]:
            msg = "Undefined plugin instance execution status: 'waiting'."
            raise KeyError(msg)
        return obj.get_plugin_instances_status_count('waiting')

    def get_scheduled_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'scheduled' status.
        """
        if 'scheduled' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: 'scheduled'.")
        return obj.get_plugin_instances_status_count('scheduled')

    def get_started_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'started' status.
        """
        if 'started' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: 'started'.")
        return obj.get_plugin_instances_status_count('started')

    def get_registering_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'registeringFiles' status.
        """
        if 'registeringFiles' not in [status[0] for status in STATUS_CHOICES]:
            msg = "Undefined plugin instance execution status: 'registeringFiles'."
            raise KeyError(msg)
        return obj.get_plugin_instances_status_count('registeringFiles')

    def get_finished_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'finishedSuccessfully' status.
        """
        if 'finishedSuccessfully' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: "
                           "'finishedSuccessfully'.")
        return obj.get_plugin_instances_status_count('finishedSuccessfully')

    def get_errored_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'finishedWithError' status.
        """
        if 'finishedWithError' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: "
                           "'finishedWithError'.")
        return obj.get_plugin_instances_status_count('finishedWithError')

    def get_cancelled_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'cancelled' status.
        """
        if 'cancelled' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: 'cancelled'.")
        return obj.get_plugin_instances_status_count('cancelled')
