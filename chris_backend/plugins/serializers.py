
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers
from collectionjson.services import collection_serializer_is_valid

from .models import Plugin, PluginParameter, PluginInstance, StringParameter
from .models import FloatParameter, IntParameter, BoolParameter, PathParameter
from .fields import MemoryInt, CPUInt
from .models import ComputeResource


class ComputeResourceSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = ComputeResource
        fields = ('url', 'compute_resource_identifier')


class PluginSerializer(serializers.HyperlinkedModelSerializer):
    parameters = serializers.HyperlinkedIdentityField(view_name='pluginparameter-list')
    instances = serializers.HyperlinkedIdentityField(view_name='plugininstance-list')
    compute_resource_identifier = serializers.ReadOnlyField(
        source='compute_resource.compute_resource_identifier')

    class Meta:
        model = Plugin
        fields = ('url', 'name', 'dock_image', 'type', 'authors', 'title', 'category',
                  'description', 'documentation', 'license', 'version',
                  'compute_resource_identifier', 'parameters', 'instances',
                  'min_number_of_workers', 'max_number_of_workers', 'min_cpu_limit',
                  'max_cpu_limit', 'min_memory_limit', 'max_memory_limit',
                  'min_gpu_limit',
                  'max_gpu_limit')

    def validate(self, data):
        """
        Overriden to validate compute-related descriptors in the plugin app representation.
        """
        # validate compute-related descriptors
        data['min_number_of_workers'] = self.validate_app_workers_descriptor(
            data['min_number_of_workers'])

        data['max_number_of_workers'] = self.validate_app_workers_descriptor(
            data['max_number_of_workers'])

        data['min_gpu_limit'] = self.validate_app_gpu_descriptor(
            data['min_gpu_limit'])

        data['max_gpu_limit'] = self.validate_app_gpu_descriptor(
            data['max_gpu_limit'])

        data['min_cpu_limit'] = self.validate_app_cpu_descriptor(
            data['min_cpu_limit'])

        data['max_cpu_limit'] = self.validate_app_cpu_descriptor(
            data['max_cpu_limit'])

        data['min_memory_limit'] = self.validate_app_memory_descriptor(
            data['min_memory_limit'])

        data['max_memory_limit'] = self.validate_app_memory_descriptor(
            data['max_memory_limit'])

        # validate descriptor limits
        err_msg = "Minimum number of workers should be less than maximum number of workers"
        self.validate_app_descriptor_limits(data, 'min_number_of_workers',
                                            'max_number_of_workers', err_msg)
        err_msg = "Minimum cpu limit should be less than maximum cpu limit"
        self.validate_app_descriptor_limits(data, 'min_cpu_limit', 'max_cpu_limit',
                                            err_msg)
        err_msg = "Minimum memory limit should be less than maximum memory limit"
        self.validate_app_descriptor_limits(data, 'min_memory_limit',
                                            'max_memory_limit', err_msg)
        err_msg = "Minimum gpu limit should be less than maximum gpu limit"
        self.validate_app_descriptor_limits(data, 'min_gpu_limit', 'max_gpu_limit',
                                            err_msg)
        return data

    @staticmethod
    def validate_app_workers_descriptor(descriptor):
        """
        Custom method to validate plugin maximum and minimum workers descriptors.
        """
        error_msg = "Minimum and maximum number of workers must be positive integers"
        int_d = PluginSerializer.validate_app_int_descriptor(descriptor, error_msg)
        if int_d < 1:
            raise serializers.ValidationError(error_msg)
        return int_d

    @staticmethod
    def validate_app_cpu_descriptor(descriptor):
        """
        Custom method to validate plugin maximum and minimum cpu descriptors.
        """
        try:
            return CPUInt(descriptor)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    @staticmethod
    def validate_app_memory_descriptor(descriptor):
        """
        Custom method to validate plugin maximum and minimum memory descriptors.
        """
        try:
            return MemoryInt(descriptor)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    @staticmethod
    def validate_app_gpu_descriptor(descriptor):
        """
        Custom method to validate plugin maximum and minimum gpu descriptors.
        """
        error_msg = "Minimum and maximum gpu must be non-negative integers"
        return PluginSerializer.validate_app_int_descriptor(descriptor, error_msg)

    @staticmethod
    def validate_app_int_descriptor(descriptor, error_msg=''):
        """
        Custom method to validate a positive integer descriptor.
        """
        try:
            int_d = int(descriptor)
            assert int_d >= 0
        except (ValueError, AssertionError):
            raise serializers.ValidationError(error_msg)
        return int_d

    @staticmethod
    def validate_app_descriptor_limits(app_repr, min_descriptor_name, max_descriptor_name,
                                       error_msg=''):
        """
        Custom method to validate that a descriptor's minimum is smaller than its maximum.
        """
        if (min_descriptor_name in app_repr) and (max_descriptor_name in app_repr) \
                and (app_repr[max_descriptor_name] < app_repr[min_descriptor_name]):
            raise serializers.ValidationError(error_msg)


class PluginParameterSerializer(serializers.HyperlinkedModelSerializer):
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)    
    class Meta:
        model = PluginParameter
        fields = ('url', 'name', 'type', 'optional', 'default', 'help', 'plugin')


class PluginInstanceSerializer(serializers.HyperlinkedModelSerializer):
    plugin_name = serializers.ReadOnlyField(source='plugin.name')
    owner = serializers.ReadOnlyField(source='owner.username')
    previous = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                   read_only=True)
    previous_id = serializers.ReadOnlyField(source='previous.id')
    compute_resource_identifier = serializers.ReadOnlyField(
        source='compute_resource.compute_resource_identifier')
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail',
                                               read_only=True)
    string_param = serializers.HyperlinkedRelatedField(many=True,
                                                       view_name='stringparameter-detail',
                                                       read_only=True)
    int_param = serializers.HyperlinkedRelatedField(many=True,
                                                    view_name='intparameter-detail',
                                                    read_only=True)
    float_param = serializers.HyperlinkedRelatedField(many=True,
                                                    view_name='floatparameter-detail',
                                                    read_only=True)
    bool_param = serializers.HyperlinkedRelatedField(many=True,
                                                    view_name='boolparameter-detail',
                                                    read_only=True)
    path_param = serializers.HyperlinkedRelatedField(many=True,
                                                       view_name='pathparameter-detail',
                                                       read_only=True)

    class Meta:
        model = PluginInstance
        fields = ('url', 'id', 'previous_id', 'plugin_name', 'start_date', 'end_date',
                  'status', 'previous', 'owner', 'feed', 'plugin',
                  'compute_resource_identifier', 'string_param', 'int_param',
                  'float_param', 'bool_param', 'path_param', 'compute_resource_id',
                  'cpu_limit', 'memory_limit', 'number_of_workers','gpu_limit')
        
    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(PluginInstanceSerializer, self).is_valid(raise_exception=raise_exception)

    def save(self, *args, **kwargs):
        """
        Overriden to provide defaults before saving instance.
        """
        plugin = self.context['view'].get_object()
        if 'gpu_limit' not in self.validated_data:
            self.validated_data['gpu_limit'] = plugin.min_gpu_limit
        if 'number_of_workers' not in self.validated_data:
            self.validated_data['number_of_workers'] = plugin.min_number_of_workers
        if 'cpu_limit' not in self.validated_data:
            self.validated_data['cpu_limit'] = CPUInt(plugin.min_cpu_limit)
        if 'memory_limit' not in self.validated_data:
            self.validated_data['memory_limit'] = MemoryInt(plugin.min_memory_limit)
        return super(PluginInstanceSerializer, self).save(*args, **kwargs)

    def validate_previous(self, previous_id, plugin):
        """
        Custom method to check that an id is provided for previous instance when
        corresponding plugin is of type 'ds'. Then check that the provided id exists in
        the DB.
        """
        previous = None
        if plugin.type=='ds':
            if not previous_id:
                raise serializers.ValidationError(
                    {'detail': "A previous plugin instance id is required"})
            try:
                pk = int(previous_id)
                previous = PluginInstance.objects.get(pk=pk)
            except (ValueError, ObjectDoesNotExist):
                raise serializers.ValidationError(
                    {'detail':
                     "Couldn't find any 'previous' plugin instance with id %s" % previous_id})
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

    def validate_value_within_interval(self, val, min_val, max_val, val_str):
        if val < min_val or val > max_val:
            raise serializers.ValidationError({'detail':"%s out of range." % val_str})


class StringParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)   
    class Meta:
        model = StringParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')


class IntParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)
    
    class Meta:
        model = IntParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')


class FloatParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)
    
    class Meta:
        model = FloatParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')


class BoolParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)
    
    class Meta:
        model = BoolParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')


class PathParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)
    class Meta:
        model = PathParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')
        

PARAMETER_SERIALIZERS={'string': StringParameterSerializer,
                       'integer': IntParameterSerializer,
                       'float': FloatParameterSerializer,
                       'boolean': BoolParameterSerializer,
                       'path': PathParameterSerializer }

