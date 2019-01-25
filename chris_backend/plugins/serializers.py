
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
        # here a piping pecedes another piping if its corresponding pluging precedes
        # the other piping's plugin in the pipeline
        #import pdb; pdb.set_trace()
        bf_plugin_id_tree = validated_data.pop('plugin_id_tree', None)
        plugin_inst_id = validated_data.pop('plugin_inst_id', None)
        pipeline = super(PipelineSerializer, self).create(validated_data)
        if bf_plugin_id_tree:
            root = bf_plugin_id_tree.pop(0)
            root_plg = Plugin.objects.get(pk=root['id'])
            root_plg_piping = PluginPiping.objects.create(pipeline=pipeline,
                                                          plugin=root_plg)
            root_plg_piping.save()
            previous_plg_id = root['id']
            previous_piping = root_plg_piping
            pipings_queue = []
            for d in bf_plugin_id_tree:
                plg = Plugin.objects.get(pk=d['id'])
                while d['previous_id'] != previous_plg_id:
                    previous_piping = pipings_queue.pop(0)
                    previous_plg_id = previous_piping.plugin.id
                plg_piping = PluginPiping.objects.create(pipeline=pipeline, plugin=plg,
                                                         previous=previous_piping)
                plg_piping.save()
                pipings_queue.append(plg_piping)
        else:


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

    def validate_plugin_id_tree(self, plugin_id_tree):
        """
        Overriden to validate the tree of plugin ids. It should be a list of dictionaries.
        Each dictionary containing the id of a node and the id of the previous node.
        """
        try:
            plugin_id_list = list(json.loads(plugin_id_tree))
        except json.decoder.JSONDecodeError:
            raise serializers.ValidationError("Invalid JSON string %s" % plugin_id_tree)
        if len(plugin_id_list) == 0:
            raise serializers.ValidationError("Invalid empty list %s" % plugin_id_tree)

        try:
            bf_plugin_id_tree = PipelineSerializer.sort_tree_list_in_breadth_first(
                plugin_id_tree)
        except (ValueError, Exception) as e:
            raise serializers.ValidationError(e)

        for d in bf_plugin_id_tree:
            plg_id = d['id']
            try:
                plg = Plugin.objects.get(pk=plg_id)
            except ObjectDoesNotExist:
                raise serializers.ValidationError("Couldn't find any plugin with id %s" %
                                                  plg_id)
            if plg.type == 'fs':
                raise serializers.ValidationError("%s is a plugin of type 'fs' and "
                                                  "therefore can not be used to create a "
                                                  "pipeline" % plg)
        return bf_plugin_id_tree

    @staticmethod
    def sort_tree_list_in_breadth_first(tree_list):
        """
        Custom method to sort the passed tree list in breadth_first order. Raises an
        exception if the represented tree is not connected.
        """
        (child_ids, root_id) = PipelineSerializer.get_child_ids(tree_list)
        sorted_tree_list = []
        queue = [{'id': root_id, 'previous_id': None}]
        while len(queue):
            cur_node = queue.pop(0)
            sorted_tree_list.append(cur_node)
            for child in child_ids[cur_node['id']]:
                queue.append({'id': child, 'previous_id': cur_node['id']})
        if len(sorted_tree_list) < len(tree_list):
            raise ValueError("Tree is not connected! Bad tree list %s." % tree_list)
        return sorted_tree_list

    @staticmethod
    def get_child_ids(tree_list):
        """
        Custom method to return a list of child ids for each id in tree_list and the
        root id of the tree.
        """
        try:
            previous_id_dict = {d['id']:d['previous_id'] for d in tree_list}
            root_id = [k for k,v in previous_id_dict.items() if not v][0]
        except IndexError:
            raise ValueError("Couldn't find any root id in %s" % tree_list)
        except Exception:
            raise ValueError("Bad tree list %s. It must be a list of dictionaries with"
                             " 'id' and 'previous_id' as keys" % tree_list)
        child_ids = {root_id: []} # dict with a list of child ids for each id entry
        previous_id_dict[root_id] = -1  # -1 a child_ids entry for id was already created
        for id in previous_id_dict:
            if previous_id_dict[id] != -1:
                child_ids[id] = []
                prev_id = previous_id_dict[id]
                previous_id_dict[id] = -1
                if previous_id_dict[prev_id] == -1:
                    child_ids[prev_id].append(id)
                else:
                    child_ids[prev_id] = [id]
        return (child_ids, root_id)


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

