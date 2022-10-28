
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from plugininstances.models import PluginInstance

from .models import PipelineInstance


class PipelineInstanceSerializer(serializers.HyperlinkedModelSerializer):
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    pipeline_name = serializers.ReadOnlyField(source='pipeline.name')
    previous_plugin_inst_id = serializers.IntegerField(
        min_value=1, write_only=True, required=False)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    pipeline = serializers.HyperlinkedRelatedField(view_name='pipeline-detail',
                                                   read_only=True)
    plugin_instances = serializers.HyperlinkedIdentityField(
        view_name='pipelineinstance-plugininstance-list')

    class Meta:
        model = PipelineInstance
        fields = (
            'url',
            'id',
            'title',
            'pipeline_id',
            'pipeline_name',
            'owner_username',
            'description',
            'previous_plugin_inst_id',
            'pipeline',
            'plugin_instances',
            'cpu_limit',
            'memory_limit',
            'number_of_workers',
            'gpu_limit')

    def create(self, validated_data):
        """
        Overriden to delete 'previous_plugin_inst_id' from serializer data as it's not
        a model field.
        """
        del validated_data['previous_plugin_inst_id']
        return super(PipelineInstanceSerializer, self).create(validated_data)

    def validate_previous_plugin_inst(self, previous_plugin_inst_id):
        """
        Custom method to check that an integer id is provided for previous instance. Then
        check that the id exists in the DB and that the user can run plugins within the
        corresponding feed.
        """
        if not previous_plugin_inst_id:
            raise serializers.ValidationError(
                {'previous_plugin_inst_id': ["This field is required."]})
        try:
            pk = int(previous_plugin_inst_id)
            previous_plugin_inst = PluginInstance.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            raise serializers.ValidationError(
                {'previous_plugin_inst_id':
                 [f"Couldn't find any 'previous' plugin instance with id {pk}."]})
        # check that the user can run plugins within this feed
        user = self.context['request'].user
        if user not in previous_plugin_inst.feed.owner.all():
            raise serializers.ValidationError(
                {
                    'previous_plugin_inst_id': [
                        "User is not an owner of feed for previous instance with id %s." %
                        previous_plugin_inst_id]})
        return previous_plugin_inst

    def parse_parameters(self):
        """
        Custom method to parse pipeline instance parameters in the request data
        dictionary.
        """
        request_data = self.context['request'].data
        # parameters name in the request have the form
        # < plugin.id > _ < piping.id > _ < previous_piping.id > _ < param.name >
        parsed_params_dict = {}
        for param in request_data:
            try:
                param_elements = param.split('_')
                id_list = param_elements[:3]
                piping_id = int(id_list[1])
            except Exception:
                pass
            else:
                param_name = '_'.join(param_elements[3:])
                if piping_id in parsed_params_dict:
                    parsed_params_dict[piping_id][param_name] = request_data[param]
                else:
                    parsed_params_dict[piping_id] = {
                        param_name: request_data[param]}
        return parsed_params_dict
