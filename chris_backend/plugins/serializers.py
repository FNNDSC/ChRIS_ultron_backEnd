
import re

from django.utils import timezone
from rest_framework import serializers

from .models import ComputeResource, PluginMeta, Plugin, PluginParameter
from .models import (DefaultFloatParameter, DefaultIntParameter, DefaultBoolParameter,
                     DefaultStrParameter)
from .fields import MemoryInt, CPUInt


class ComputeResourceSerializer(serializers.HyperlinkedModelSerializer):
    compute_user = serializers.CharField(min_length=4, max_length=32, write_only=True)
    compute_password = serializers.CharField(min_length=8, max_length=100,
                                             write_only=True)
    compute_auth_token = serializers.CharField(max_length=500, write_only=True,
                                               required=False)

    class Meta:
        model = ComputeResource
        fields = ('url', 'id', 'creation_date', 'modification_date', 'name',
                  'compute_url', 'compute_auth_url', 'compute_innetwork', 'compute_user',
                  'compute_password', 'compute_auth_token', 'description',
                  'max_job_exec_seconds')


class PluginMetaSerializer(serializers.HyperlinkedModelSerializer):
    plugins = serializers.HyperlinkedIdentityField(view_name='pluginmeta-plugin-list')

    class Meta:
        model = PluginMeta
        fields = ('url', 'id', 'creation_date', 'modification_date', 'name', 'title',
                  'stars', 'public_repo', 'license', 'type', 'icon', 'category',
                  'authors', 'documentation', 'plugins')

    def update(self, instance, validated_data):
        """
        Overriden to add modification date.
        """
        instance.modification_date = timezone.now()
        instance.save()
        return super(PluginMetaSerializer, self).update(instance, validated_data)


class PluginSerializer(serializers.HyperlinkedModelSerializer):
    name = serializers.ReadOnlyField(source='meta.name')
    title = serializers.ReadOnlyField(source='meta.title')
    public_repo = serializers.ReadOnlyField(source='meta.public_repo')
    license = serializers.ReadOnlyField(source='meta.license')
    type = serializers.ReadOnlyField(source='meta.type')
    icon = serializers.ReadOnlyField(source='meta.icon')
    category = serializers.ReadOnlyField(source='meta.category')
    authors = serializers.ReadOnlyField(source='meta.authors')
    documentation = serializers.ReadOnlyField(source='meta.documentation')
    stars = serializers.ReadOnlyField(source='meta.stars')
    meta = serializers.HyperlinkedRelatedField(view_name='pluginmeta-detail',
                                               read_only=True)
    parameters = serializers.HyperlinkedIdentityField(view_name='pluginparameter-list')
    instances = serializers.HyperlinkedIdentityField(view_name='plugininstance-list')
    compute_resources = serializers.HyperlinkedIdentityField(
        view_name='plugin-computeresource-list')

    class Meta:
        model = Plugin
        fields = ('url', 'id', 'creation_date', 'name', 'version', 'dock_image',
                  'public_repo', 'icon', 'type', 'stars', 'authors', 'title', 'category',
                  'description', 'documentation', 'license',  'execshell', 'selfpath',
                  'selfexec', 'min_number_of_workers', 'max_number_of_workers',
                  'min_cpu_limit', 'max_cpu_limit', 'min_memory_limit',
                  'max_memory_limit', 'min_gpu_limit', 'max_gpu_limit', 'meta',
                  'parameters', 'instances', 'compute_resources')

    def validate(self, data):
        """
        Overriden to validate compute-related descriptors in the plugin app
        representation.
        """
        # validate compute-related descriptors
        if 'min_number_of_workers' in data:
            data['min_number_of_workers'] = self.validate_app_workers_descriptor(
                {'name': 'min_number_of_workers', 'value': data['min_number_of_workers']})

        if 'max_number_of_workers' in data:
            data['max_number_of_workers'] = self.validate_app_workers_descriptor(
                {'name': 'max_number_of_workers', 'value': data['max_number_of_workers']})

        if 'min_gpu_limit' in data:
            data['min_gpu_limit'] = self.validate_app_gpu_descriptor(
                {'name': 'min_gpu_limit', 'value': data['min_gpu_limit']})

        if 'max_gpu_limit' in data:
            data['max_gpu_limit'] = self.validate_app_gpu_descriptor(
                {'name': 'max_gpu_limit', 'value': data['max_gpu_limit']})

        if 'min_cpu_limit' in data:
            data['min_cpu_limit'] = self.validate_app_cpu_descriptor(
                {'name': 'min_cpu_limit', 'value': data['min_cpu_limit']})

        if 'max_cpu_limit' in data:
            data['max_cpu_limit'] = self.validate_app_cpu_descriptor(
                {'name': 'max_cpu_limit', 'value': data['max_cpu_limit']})

        if 'min_memory_limit' in data:
            data['min_memory_limit'] = self.validate_app_memory_descriptor(
                {'name': 'min_memory_limit', 'value': data['min_memory_limit']})

        if 'max_memory_limit' in data:
            data['max_memory_limit'] = self.validate_app_memory_descriptor(
                {'name': 'max_memory_limit', 'value': data['max_memory_limit']})

        # validate descriptor limits
        err_msg = "Minimum number of workers should be less than maximum number of " \
                  "workers."
        self.validate_app_descriptor_limits(data, 'min_number_of_workers',
                                            'max_number_of_workers', err_msg)
        err_msg = "Minimum cpu limit should be less than maximum cpu limit."
        self.validate_app_descriptor_limits(data, 'min_cpu_limit', 'max_cpu_limit',
                                            err_msg)
        err_msg = "Minimum memory limit should be less than maximum memory limit."
        self.validate_app_descriptor_limits(data, 'min_memory_limit',
                                            'max_memory_limit', err_msg)
        err_msg = "Minimum gpu limit should be less than maximum gpu limit."
        self.validate_app_descriptor_limits(data, 'min_gpu_limit', 'max_gpu_limit',
                                            err_msg)
        return data

    def validate_version(self, version):
        """
        Overriden to check that a proper version type and format has been submitted.
        """
        if not isinstance(version, str):
            raise serializers.ValidationError(["Invalid type for plugin app version "
                                               "field. Must be a string."])
        if not re.match(r"^[0-9.]+$", version):
            raise serializers.ValidationError(["Invalid plugin app version number "
                                               "format %s." % version])
        return version

    @staticmethod
    def validate_app_workers_descriptor(descriptor_dict):
        """
        Custom method to validate plugin maximum and minimum workers descriptors.
        """
        error_msg = "This field must be a positive integer."
        int_d = PluginSerializer.validate_app_int_descriptor(descriptor_dict, error_msg)
        if int_d < 1:
            raise serializers.ValidationError({descriptor_dict['name']: [error_msg]})
        return int_d

    @staticmethod
    def validate_app_cpu_descriptor(descriptor_dict):
        """
        Custom method to validate plugin maximum and minimum cpu descriptors.
        """
        try:
            return CPUInt(descriptor_dict['value'])
        except ValueError as e:
            raise serializers.ValidationError({descriptor_dict['name']: [str(e)]})

    @staticmethod
    def validate_app_memory_descriptor(descriptor_dict):
        """
        Custom method to validate plugin maximum and minimum memory descriptors.
        """
        try:
            return MemoryInt(descriptor_dict['value'])
        except ValueError as e:
            raise serializers.ValidationError({descriptor_dict['name']: [str(e)]})

    @staticmethod
    def validate_app_gpu_descriptor(descriptor_dict):
        """
        Custom method to validate plugin maximum and minimum gpu descriptors.
        """
        error_msg = "This field must be a non-negative integer."
        return PluginSerializer.validate_app_int_descriptor(descriptor_dict, error_msg)

    @staticmethod
    def validate_app_int_descriptor(descriptor_dict, error_msg):
        """
        Custom method to validate a positive integer descriptor.
        """
        try:
            int_d = int(descriptor_dict['value'])
            assert int_d >= 0
        except (ValueError, AssertionError):
            raise serializers.ValidationError({descriptor_dict['name']: [error_msg]})
        return int_d

    @staticmethod
    def validate_app_descriptor_limits(app_repr, min_descriptor_name, max_descriptor_name,
                                       error_msg=''):
        """
        Custom method to validate that a descriptor's minimum is smaller than its maximum.
        """
        if (min_descriptor_name in app_repr) and (max_descriptor_name in app_repr) \
                and (app_repr[max_descriptor_name] < app_repr[min_descriptor_name]):
            raise serializers.ValidationError({'non_field_errors': [error_msg]})


class PluginParameterSerializer(serializers.HyperlinkedModelSerializer):
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)
    default = serializers.SerializerMethodField()

    class Meta:
        model = PluginParameter
        fields = ('url', 'id', 'name', 'type', 'optional', 'default', 'flag',
                  'short_flag', 'action', 'help', 'ui_exposed', 'plugin')

    def validate(self, data):
        """
        Overriden to check that optional is always false for parameters of type 'path'
        and 'unextpath'.
        """
        optional = data.get('optional')
        param_type = data.get('type')
        if optional and param_type in ('path', 'unextpath'):
            error_msg = "Parameters of type 'path' or 'unextpath' cannot be optional."
            raise serializers.ValidationError({'non_field_errors': [error_msg]})
        return data

    def get_default(self, obj) -> str | int | float | bool | None:
        """
        Overriden to get the default parameter value regardless of type.
        """
        default = obj.get_default()
        return default.value if default else None


class DefaultStrParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultStrParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_param')


class DefaultIntParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultIntParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_param')


class DefaultFloatParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultFloatParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_param')


class DefaultBoolParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultBoolParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_param')


DEFAULT_PARAMETER_SERIALIZERS = {'string': DefaultStrParameterSerializer,
                                 'integer': DefaultIntParameterSerializer,
                                 'float': DefaultFloatParameterSerializer,
                                 'boolean': DefaultBoolParameterSerializer}
