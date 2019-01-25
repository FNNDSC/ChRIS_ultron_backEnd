
import json

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from collectionjson.services import collection_serializer_is_valid
from plugininstances.models import PluginInstance

from .models import Plugin, PluginParameter
from .models import ComputeResource
from .models import Pipeline, PluginPiping
from .fields import MemoryInt, CPUInt


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
        fields = ('url', 'id', 'name', 'dock_image', 'type', 'authors', 'title', 'category',
                  'description', 'documentation', 'license', 'version', 'execshell',
                  'selfpath', 'selfexec', 'compute_resource_identifier', 'parameters',
                  'instances', 'min_number_of_workers', 'max_number_of_workers',
                  'min_cpu_limit', 'max_cpu_limit', 'min_memory_limit',
                  'max_memory_limit', 'min_gpu_limit', 'max_gpu_limit')

    def validate(self, data):
        """
        Overriden to validate compute-related descriptors in the plugin app
        representation.
        """
        # validate compute-related descriptors
        if 'min_number_of_workers' in data:
            data['min_number_of_workers'] = self.validate_app_workers_descriptor(
                data['min_number_of_workers'])

        if 'max_number_of_workers' in data:
            data['max_number_of_workers'] = self.validate_app_workers_descriptor(
                data['max_number_of_workers'])

        if 'min_gpu_limit' in data:
            data['min_gpu_limit'] = self.validate_app_gpu_descriptor(
                data['min_gpu_limit'])

        if 'max_gpu_limit' in data:
            data['max_gpu_limit'] = self.validate_app_gpu_descriptor(
                data['max_gpu_limit'])

        if 'min_cpu_limit' in data:
            data['min_cpu_limit'] = self.validate_app_cpu_descriptor(
                data['min_cpu_limit'])

        if 'max_cpu_limit' in data:
            data['max_cpu_limit'] = self.validate_app_cpu_descriptor(
            data['max_cpu_limit'])

        if 'min_memory_limit' in data:
            data['min_memory_limit'] = self.validate_app_memory_descriptor(
                data['min_memory_limit'])

        if 'max_memory_limit' in data:
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
        fields = ('url', 'id', 'name', 'type', 'optional', 'default', 'flag', 'action',
                  'help', 'plugin')


class PipelineSerializer(serializers.HyperlinkedModelSerializer):
    plugin_id_tree = serializers.JSONField(write_only=True, required=False)
    plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True,
                                              required=False)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    plugins = serializers.HyperlinkedIdentityField(view_name='pipeline-plugin-list')
    plugin_tree = serializers.HyperlinkedIdentityField(
        view_name='pipeline-pluginpiping-list')

    class Meta:
        model = Pipeline
        fields = ('url', 'id', 'name', 'authors', 'category', 'description',
                  'plugin_id_tree', 'plugin_inst_id', 'owner_username', 'plugins',
                  'plugin_tree')

    def create(self, validated_data):
        """
        Overriden to create the pipeline and associate to it all the plugins in the
        passed list in the same order as they appear in the list.
        """
        #import pdb; pdb.set_trace()
        plugins_from_id_list = validated_data.pop('plugin_id_list', None)
        plugins_from_inst_id = validated_data.pop('plugin_inst_id', None)
        if plugins_from_id_list:
            plugins = plugins_from_id_list
        else:
            plugins = plugins_from_inst_id
        pipeline = super(PipelineSerializer, self).create(validated_data)
        i = 0
        for plg in plugins:
            plg_piping = PluginPiping.objects.create(pipeline=pipeline, plugin=plg,
                                                     position=i)
            plg_piping.save()
            i += 1
        return pipeline

    def update(self, instance, validated_data):
        """
        Overriden to remove parameters that are not allowed to be used on update.
        """
        validated_data.pop('plugin_id_list', None)
        validated_data.pop('plugin_inst_id', None)
        return super(PipelineSerializer, self).update(instance, validated_data)

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors.
        """
        return super(PipelineSerializer, self).is_valid(raise_exception=raise_exception)

    def validate(self, data):
        """
        Overriden to validate that some fields are in data.
        """
        plugin_id_tree = data.pop('plugin_id_tree', None)
        plugis_inst_id = data.pop('plugin_inst_id', None)
        if not plugin_id_tree and not plugis_inst_id:
            raise serializers.ValidationError("At least one of the fields "
                                              "'plugin_id_tree' or 'plugin_inst_id' must "
                                              "be provided")
        return data

    def validate_plugin_id_list(self, plugin_id_tree):
        """
        Overriden to validate the tree of plugin ids.
        """
        plugins = []
        try:
            plugin_ids = list(json.loads(plugin_id_tree))
            if len(plugin_ids) == 0:
                raise Exception("Invalid empty list %s" % plugin_id_tree)
            for id in plugin_ids:
                plg = Plugin.objects.get(pk=id)
                if plg.type == 'fs':
                    raise Exception("%s is a plugin of type 'fs' and therefore can not "
                                    "be used to create a pipeline" % plg)
                plugins.append(plg)
        except json.decoder.JSONDecodeError:
            err_str = "Invalid JSON string %s"
            raise serializers.ValidationError({err_str % plugin_id_list})
        except (ValueError, ObjectDoesNotExist):
            err_str = "Couldn't find any plugin with id %s"
            raise serializers.ValidationError({err_str % id})
        except Exception as e:
            raise serializers.ValidationError(e)
        return plugins

    def validate_plugin_inst_id(self, plugin_inst_id):
        """
        Overriden to validate the plugin instance id.
        """
        try:
            plg_inst = PluginInstance.objects.get(pk=plugin_inst_id)
        except ObjectDoesNotExist:
            raise serializers.ValidationError("Couldn't find any plugin instance with id "
                                              "%s" % plugin_inst_id)
        plg = plg_inst.plugin
        if plg.type == 'fs':
            raise serializers.ValidationError("%s is a plugin of type 'fs' and therefore "
                                              "can not be used as the root of a new "
                                              "pipeline" % plg.name)
        return plg_inst

    @staticmethod
    def validate_tree(tree_list):
        """
        Custom method to validate a tree wich is a list of dictionaries. Each dictionary
        containing the id of a node and the id of the previous node.
        """
        tree = {}
        id_dict = {d['id']:d['previous_id'] for d in tree_list}
        root_id = [k for k,v in id_dict.items() if v is None][0]
        tree[root_id] = []
        id_dict[root_id] = -1  # -1 means a node for this id was already created
        for id in id_dict:
            if id_dict[id] != -1:
                previous_id = id_dict[id]
                if id_dict[previous_id] == -1:
                    tree[previous_id].append(id)
                else:
                    tree[previous_id]=[id]





class PluginPipingSerializer(serializers.HyperlinkedModelSerializer):
    plugin_id = serializers.ReadOnlyField(source='plugin.id')
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    previous_id = serializers.ReadOnlyField(source='previous.id')
    previous = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                 read_only=True)
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)
    pipeline = serializers.HyperlinkedRelatedField(view_name='pipeline-detail',
                                                   read_only=True)

    class Meta:
        model = PluginPiping
        fields = ('url', 'id', 'plugin_id', 'pipeline_id', 'previous_id', 'previous',
                  'plugin', 'pipeline')

