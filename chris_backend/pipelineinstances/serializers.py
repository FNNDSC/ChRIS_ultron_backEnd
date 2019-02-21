
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from collectionjson.services import collection_serializer_is_valid
from plugininstances.models import PluginInstance
from .models import PipelineInstance


class PipelineInstanceSerializer(serializers.HyperlinkedModelSerializer):
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    previous_plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True)
    pipeline = serializers.HyperlinkedRelatedField(view_name='pipeline-detail',
                                                   read_only=True)
    plugin_instances = serializers.HyperlinkedIdentityField(
        view_name='pipelineinstance-plugininstance-list')

    class Meta:
        model = PipelineInstance
        fields = ('url', 'id', 'title', 'pipeline_id', 'description',
                  'previous_plugin_inst_id', 'pipeline', 'plugin_instances')

    def create(self, validated_data):
        """
        Overriden to delete 'previous_plugin_inst_id' from serializer data as it's not
        a model field.
        """
        del validated_data['previous_plugin_inst_id']
        return super(PipelineInstanceSerializer, self).create(validated_data)

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors.
        """
        return super(PipelineInstanceSerializer, self).is_valid(
            raise_exception=raise_exception)

    def validate_previous_plugin_inst(self, previous_plugin_inst_id):
        """
        Custom method to check that an integer id is provided for previous instance. Then
        check that the id exists in the DB and that the user can run plugins within the
        corresponding feed.
        """
        if not previous_plugin_inst_id:
            raise serializers.ValidationError(
                {'detail': "A previous plugin instance id is required"})
        try:
            pk = int(previous_plugin_inst_id)
            previous_plugin_inst = PluginInstance.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            err_str = "Couldn't find any 'previous' plugin instance with id %s"
            raise serializers.ValidationError(
                {'detail': err_str % previous_plugin_inst_id})
        # check that the user can run plugins within this feed
        user = self.context['request'].user
        if user not in previous_plugin_inst.feed.owner.all():
            err_str = "User is not an owner of feed for previous instance with id %s"
            raise serializers.ValidationError(
                {'detail': err_str % previous_plugin_inst_id})
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
                id_list = param.split('_')[:3]
                piping_id = int(id_list[1])
            except Exception:
                pass
            else:
                param_name = '_'.join(id_list[3:])
                if piping_id in parsed_params_dict:
                    parsed_params_dict[piping_id][param_name] = request_data[param]
                else:
                    parsed_params_dict[piping_id] = {param_name: request_data[param]}
        return parsed_params_dict
