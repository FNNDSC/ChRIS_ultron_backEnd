
import os

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.reverse import reverse

from collectionjson.services import collection_serializer_is_valid
from collectionjson.fields import ItemLinkField

from plugins.models import TYPES
from plugins.fields import MemoryInt, CPUInt
from .models import PluginInstance, PluginInstanceFile
from .models import FloatParameter, IntParameter, BoolParameter
from .models import PathParameter, StrParameter
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

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
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

    @staticmethod
    def parse_parameters(request_data):
        """
        Custom method to parse pipeline instance parameters in a request data
        dictionary.
        """
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


class PluginInstanceSerializer(serializers.HyperlinkedModelSerializer):
    previous_id = serializers.ReadOnlyField(source='previous.id')
    plugin_id = serializers.ReadOnlyField(source='plugin.id')
    plugin_name = serializers.ReadOnlyField(source='plugin.name')
    pipeline_id = serializers.ReadOnlyField(source='pipeline_inst.pipeline.id')
    pipeline_name = serializers.ReadOnlyField(source='pipeline_inst.pipeline.name')
    pipeline_inst_id = serializers.ReadOnlyField(source='pipeline_inst.id')
    feed_id = serializers.ReadOnlyField(source='feed.id')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    compute_resource_identifier = serializers.ReadOnlyField(
        source='compute_resource.compute_resource_identifier')
    previous = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                   read_only=True)
    descendants = serializers.HyperlinkedIdentityField(
        view_name='plugininstance-descendant-list')
    parameters = serializers.HyperlinkedIdentityField(
        view_name='plugininstance-parameter-list')
    files = serializers.HyperlinkedIdentityField(
        view_name='plugininstancefile-list')
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)
    pipeline_inst = serializers.HyperlinkedRelatedField(
        view_name='pipelineinstance-detail', read_only=True)
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail',
                                               read_only=True)

    class Meta:
        model = PluginInstance
        fields = ('url', 'id', 'title', 'previous_id', 'plugin_id', 'plugin_name',
                  'pipeline_id', 'pipeline_name', 'pipeline_inst_id', 'pipeline_inst',
                  'feed_id', 'start_date', 'end_date', 'status', 'owner_username',
                  'previous', 'feed', 'plugin', 'descendants', 'files', 'parameters',
                  'compute_resource_identifier', 'cpu_limit', 'memory_limit',
                  'number_of_workers','gpu_limit')

    def create(self, validated_data):
        """
        Overriden to provide compute-related defaults before creating a new plugin
        instance.
        """
        plugin = self.context['view'].get_object()

        if 'gpu_limit' not in validated_data:
            validated_data['gpu_limit'] = plugin.min_gpu_limit
        if 'number_of_workers' not in validated_data:
            validated_data['number_of_workers'] = plugin.min_number_of_workers
        if 'cpu_limit' not in validated_data:
            validated_data['cpu_limit'] = CPUInt(plugin.min_cpu_limit)
        if 'memory_limit' not in validated_data:
            validated_data['memory_limit'] = MemoryInt(plugin.min_memory_limit)

        return super(PluginInstanceSerializer, self).create(validated_data)

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(PluginInstanceSerializer, self).is_valid(raise_exception=raise_exception)

    def validate_previous(self, previous_id):
        """
        Custom method to check that an id is provided for previous instance when
        corresponding plugin is of type 'ds'. Then check that the provided id exists in
        the DB and that the user can run plugins within this feed.
        """
        # using self.context['view'] in validators prevents calling is_valid when creating
        # a new serializer instance outside the Django view framework. But here is fine
        # as plugin instances are always created through the API
        plugin = self.context['view'].get_object()
        previous = None
        if plugin.type=='ds':
            if not previous_id:
                raise serializers.ValidationError(
                    {'detail': "A previous plugin instance id is required"})
            try:
                pk = int(previous_id)
                previous = PluginInstance.objects.get(pk=pk)
            except (ValueError, ObjectDoesNotExist):
                err_str = "Couldn't find any 'previous' plugin instance with id %s"
                raise serializers.ValidationError(
                    {'detail': err_str % previous_id})
            # check that the user can run plugins within this feed
            user = self.context['request'].user
            if user not in previous.feed.owner.all():
                err_str = "User is not an owner of feed for previous instance with id %s"
                raise serializers.ValidationError(
                    {'detail': err_str % previous_id})
        return previous

    def validate_gpu_limit(self, gpu_limit):
        plugin = self.context['view'].get_object()
        self.validate_value_within_interval(gpu_limit,
                                            plugin.min_gpu_limit,
                                            plugin.max_gpu_limit,
                                            'gpu_limit')
        return gpu_limit

    def validate_number_of_workers(self, number_of_workers):
        plugin = self.context['view'].get_object()
        self.validate_value_within_interval(number_of_workers,
                                            plugin.min_number_of_workers,
                                            plugin.max_number_of_workers,
                                            'number_of_workers')
        return number_of_workers

    def validate_cpu_limit(self, cpu_limit):
        plugin = self.context['view'].get_object()
        self.validate_value_within_interval(cpu_limit,
                                            plugin.min_cpu_limit,
                                            plugin.max_cpu_limit,
                                            'cpu_limit')
        return cpu_limit

    def validate_memory_limit(self, memory_limit):
        plugin = self.context['view'].get_object()
        self.validate_value_within_interval(memory_limit,
                                            plugin.min_memory_limit,
                                            plugin.max_memory_limit,
                                            'memory_limit')
        return memory_limit

    @staticmethod
    def validate_value_within_interval(val, min_val, max_val, val_str):
        if val < min_val or val > max_val:
            raise serializers.ValidationError({'detail':"%s out of range." % val_str})


class PluginInstanceFileSerializer(serializers.HyperlinkedModelSerializer):
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                      read_only=True)
    file_resource = ItemLinkField('_get_file_link')
    fname = serializers.FileField(use_url=False)
    feed_id = serializers.ReadOnlyField(source='plugin_inst.feed.id')
    plugin_inst_id = serializers.ReadOnlyField(source='plugin_inst.id')

    class Meta:
        model = PluginInstanceFile
        fields = ('url', 'id', 'fname', 'feed_id', 'plugin_inst_id', 'file_resource',
                  'plugin_inst')

    def _get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource
        """
        fields = self.fields.items()
        # get the current url
        url_field = [v for (k, v) in fields if k == 'url'][0]
        view = url_field.view_name
        request = self.context['request']
        format = self.context['format']
        url = url_field.get_url(obj, view, request, format)
        # return url = current url + file name
        return url + os.path.basename(obj.fname.name)


class StrParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.SerializerMethodField()
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = StrParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    @staticmethod
    def get_type(obj):
        return obj.plugin_param.type


class IntParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.SerializerMethodField()
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = IntParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    @staticmethod
    def get_type(obj):
        return obj.plugin_param.type


class FloatParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.SerializerMethodField()
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = FloatParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    @staticmethod
    def get_type(obj):
        return obj.plugin_param.type


class BoolParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.SerializerMethodField()
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = BoolParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    @staticmethod
    def get_type(obj):
        return obj.plugin_param.type


class PathParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.SerializerMethodField()
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = PathParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    @staticmethod
    def get_type(obj):
        return obj.plugin_param.type


class GenericParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()
    url = ItemLinkField('_get_url')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                      read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = StrParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    def _get_url(self, obj):
        """
        Custom method to get the correct url for the serialized object regardless of
        its type.
        """
        request = self.context['request']
        # here parameter detail view names are assumed to follow a convention
        view_name = TYPES[obj.plugin_param.type] + 'parameter-detail'
        return reverse(view_name, request=request, kwargs={"pk": obj.id})

    def get_value(self, obj):
        """
        Overriden to get the default parameter value regardless of its type.
        """
        return obj.value

    @staticmethod
    def get_type(obj):
        return obj.plugin_param.type
        

PARAMETER_SERIALIZERS = {'string': StrParameterSerializer,
                         'integer': IntParameterSerializer,
                         'float': FloatParameterSerializer,
                         'boolean': BoolParameterSerializer,
                         'path': PathParameterSerializer}
