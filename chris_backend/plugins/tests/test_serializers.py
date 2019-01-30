
import logging
from unittest import mock

from django.test import TestCase
from django.contrib.auth.models import User

from rest_framework import serializers

from plugininstances.models import PluginInstance
from plugins.models import Plugin, PluginParameter, ComputeResource, Pipeline
from plugins.serializers import PluginSerializer, PipelineSerializer


class SerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.plugin_name = "simplefsapp"
        self.plugin_repr = {"name": "simplefsapp", "dock_image": "fnndsc/pl-simplefsapp",
                            "authors": "FNNDSC (dev@babyMRI.org)", "type": "fs",
                            "description": "A simple chris fs app demo", "version": "0.1",
                            "title": "Simple chris fs app", "license": "Opensource (MIT)",

                            "parameters": [{"optional": True, "action": "store",
                                            "help": "look up directory", "type": "path",
                                            "name": "dir", "flag": "--dir",
                                            "default": "./"}],

                            "selfpath": "/usr/src/simplefsapp",
                            "selfexec": "simplefsapp.py", "execshell": "python3"}

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create a plugin
        data = self.plugin_repr.copy()
        parameters = self.plugin_repr['parameters']
        del data['parameters']
        data['compute_resource'] = self.compute_resource
        (plugin, tf) = Plugin.objects.get_or_create(**data)

        # add plugin's parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'])

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PluginSerializerTests(SerializerTests):

    def test_validate_app_workers_descriptor(self):
        """
        Test whether custom validate_app_workers_descriptor method raises a ValidationError
        when the app worker descriptor cannot be converted to a positive integer.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_workers_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_workers_descriptor(0)

    def test_validate_app_cpu_descriptor(self):
        """
        Test whether custom validate_app_cpu_descriptor method raises a ValidationError
        when the app cpu descriptor cannot be converted to a fields.CPUInt.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_cpu_descriptor('100me')
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor('100m'))

    def test_validate_app_memory_descriptor(self):
        """
        Test whether custom validate_app_memory_descriptor method raises a ValidationError
        when the app memory descriptor cannot be converted to a fields.MemoryInt.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_cpu_descriptor('100me')
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor('100mi'))
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor('100gi'))

    def test_validate_app_gpu_descriptor(self):
        """
        Test whether custom validate_app_gpu_descriptor method raises a ValidationError
        when the gpu descriptor cannot be converted to a non-negative integer.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_gpu_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_gpu_descriptor(-1)

    def test_validate_app_int_descriptor(self):
        """
        Test whether custom validate_app_int_descriptor method raises a ValidationError
        when the descriptor cannot be converted to a non-negative integer.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_int_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_int_descriptor(-1)

    def test_validate_app_descriptor_limits(self):
        """
        Test whether custom validate_app_descriptor_limit method raises a ValidationError
        when the max limit is smaller than the min limit.
        """
        self.plugin_repr['min_cpu_limit'] = 200
        self.plugin_repr['max_cpu_limit'] = 100
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_descriptor_limits(self.plugin_repr,
                                                            'min_cpu_limit',
                                                            'max_cpu_limit')

    def test_validate_workers_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_number_of_workers' is smaller than the 'min_number_of_workers'.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        self.plugin_repr['min_number_of_workers'] = 2
        self.plugin_repr['max_number_of_workers'] = 1
        data = self.plugin_repr.copy()
        del data['parameters']
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate(data)

    def test_validate_cpu_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_cpu_limit' is smaller than the 'min_cpu_limit'.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        self.plugin_repr['min_cpu_limit'] = 200
        self.plugin_repr['max_cpu_limit'] = 100
        data = self.plugin_repr.copy()
        del data['parameters']
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate(data)

    def test_validate_memory_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_memory_limit' is smaller than the 'min_memory_limit'.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        self.plugin_repr['min_memory_limit'] = 100000
        self.plugin_repr['max_memory_limit'] = 10000
        data = self.plugin_repr.copy()
        del data['parameters']
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate(data)

    def test_validate_gpu_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_gpu_limit' is smaller than the 'max_gpu_limit'.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        self.plugin_repr['min_gpu_limit'] = 2
        self.plugin_repr['max_gpu_limit'] = 1
        data = self.plugin_repr.copy()
        del data['parameters']
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate(data)

    def test_validate_validates_min_number_of_workers(self):
        """
        Test whether custom validate method validates the 'min_number_of_workers'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_number_of_workers'] = 4
        plg_serializer.validate_app_workers_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_workers_descriptor.assert_called_with(4)

    def test_validate_validates_max_number_of_workers(self):
        """
        Test whether custom validate method validates the 'max_number_of_workers'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_number_of_workers'] = 5
        plg_serializer.validate_app_workers_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_workers_descriptor.assert_called_with(5)

    def test_validate_validates_min_gpu_limit(self):
        """
        Test whether custom validate method validates the 'min_gpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_gpu_limit'] = 1
        plg_serializer.validate_app_gpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_gpu_descriptor.assert_called_with(1)

    def test_validate_validates_max_gpu_limit(self):
        """
        Test whether custom validate method validates the 'max_gpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_gpu_limit'] = 2
        plg_serializer.validate_app_gpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_gpu_descriptor.assert_called_with(2)

    def test_validate_validates_min_cpu_limit(self):
        """
        Test whether custom validate method validates the 'min_cpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_cpu_limit'] = 100
        plg_serializer.validate_app_cpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_cpu_descriptor.assert_called_with(100)

    def test_validate_validates_max_cpu_limit(self):
        """
        Test whether custom validate method validates the 'max_cpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_cpu_limit'] = 200
        plg_serializer.validate_app_cpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_cpu_descriptor.assert_called_with(200)

    def test_validate_validates_min_memory_limit(self):
        """
        Test whether custom validate method validates the 'min_memory_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_memory_limit'] = 10000
        plg_serializer.validate_app_memory_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_memory_descriptor.assert_called_with(10000)

    def test_validate_validates_max_memory_limit(self):
        """
        Test whether custom validate method validates the 'max_memory_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_memory_limit'] = 100000
        plg_serializer.validate_app_memory_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_memory_descriptor.assert_called_with(100000)


class PipelineSerializerTests(SerializerTests):

    def setUp(self):
        super(PipelineSerializerTests, self).setUp()
        self.username = 'foo'
        self.password = 'bar'
        self.pipeline_name = 'Pipeline1'
        user = User.objects.create_user(username=self.username, password=self.password)
        Pipeline.objects.get_or_create(name=self.pipeline_name, owner=user)

    def test_create(self):
        """
        Test whether overriden 'create' method successfully creates a new pipeline
        with a tree of associated plugins.
        """
        (plugin_ds1, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        (plugin_ds2, tf) = Plugin.objects.get_or_create(name="mri_analyze", type="ds",
                                                compute_resource=self.compute_resource)
        owner = User.objects.get(username=self.username)
        plugin_id_tree = '[{"plugin_id": ' + str(plugin_ds1.id) + \
                         ', "previous_index": null}, {"plugin_id": ' + \
                         str(plugin_ds2.id) + ', "previous_index": 0}]'
        data = {'name': 'Pipeline2', 'owner': owner, 'plugin_id_tree': plugin_id_tree}

        pipeline_serializer = PipelineSerializer(data=data)
        pipeline_serializer.is_valid(raise_exception=True)
        pipeline = pipeline_serializer.create(pipeline_serializer.validated_data)
        pipeline_plg_names = [plugin.name for plugin in pipeline.plugins.all()]
        self.assertIn("mri_convert", pipeline_plg_names)
        self.assertIn("mri_analyze", pipeline_plg_names)

    def test_update(self):
        """
        Test whether overriden 'update' method successfully updates an existing pipeline
        even when 'validated_data' argument contains 'plugin_id_tree' and
        'plugin_inst_id'.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        validated_data = {'name': 'Pipeline2', 'plugin_id_tree': {'root_index': 0},
                          'plugin_inst_id': 1}
        pipeline_serializer.update(pipeline, validated_data)
        self.assertEqual(pipeline.name, 'Pipeline2')

    def test_validate_validates_required_fields_on_create(self):
        """
        Test whether overriden validate method validates that at least one of the fields
        'plugin_id_tree' or 'plugin_inst_id' must be provided when creating a new
        pipeline.
        """
        owner = User.objects.get(username=self.username)
        data = {'name': 'Pipeline2', 'owner': owner}
        pipeline_serializer = PipelineSerializer(data=data)
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate(data)

    def test_validate_plugin_inst_id(self):
        """
        Test whether overriden validate_plugin_inst_id method validates that the plugin
        instance id corresponds to a plugin instance that is in the DB and is not of type
        'fs'.
        """
        owner = User.objects.get(username=self.username)
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_fs = Plugin.objects.get(name=self.plugin_name)
        (plugin_fs_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin_fs,
                                                                    owner=owner,
                                                compute_resource=self.compute_resource)
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_inst_id(plugin_fs_inst.id + 1)
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_inst_id(plugin_fs_inst.id)

    def test_validate_plugin_id_tree_is_json_string(self):
        """
        Test whether overriden validate_plugin_id_tree method validates that the plugin
        tree string is a proper JSON string.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        tree = '[{plugin_id: 8, "previous_index": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_id_tree(tree)

    def test_validate_plugin_id_tree_does_not_contain_empty_list(self):
        """
        Test whether overriden validate_plugin_id_tree method validates that the plugin
        tree is not an empty list.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        tree = '[]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_id_tree(tree)

    def test_validate_plugin_id_tree_plugins_exist_and_not_fs(self):
        """
        Test whether overriden validate_plugin_id_tree method validates that the plugin
        tree contains existing plugins that are not of type 'fs'.
        """
        plugin_fs = Plugin.objects.get(name=self.plugin_name)
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        tree = '[{"plugin_id": ' + str(plugin_fs.id + 1) + ', "previous_index": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_id_tree(tree)
        tree = '[{"plugin_id": ' + str(plugin_fs.id) + ', "previous_index": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_id_tree(tree)

    def test_validate_plugin_id_tree_raises_validation_error_if_get_tree_raises_value_error(self):
        """
        Test whether overriden validate_plugin_id_tree method raises ValidationError if
        internal call to get_tree method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        (plugin_ds, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', "previous_index": null}]'
        with mock.patch('plugins.serializers.PipelineSerializer.get_tree') as get_tree_mock:
            get_tree_mock.side_effect = ValueError
            with self.assertRaises(serializers.ValidationError):
                pipeline_serializer.validate_plugin_id_tree(tree)
            get_tree_mock.assert_called_with([{"plugin_id": plugin_ds.id,
                                               "previous_index": None}])

    def test_validate_plugin_id_tree_raises_validation_error_if_validate_tree_raises_value_error(self):
        """
        Test whether overriden validate_plugin_id_tree method raises ValidationError if
        internal call to validate_tree method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        (plugin_ds, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', "previous_index": null}]'
        tree_dict = {'root_index': 0, 'tree': [{"plugin_id": plugin_ds.id, "child_indices": []}]}
        with mock.patch('plugins.serializers.PipelineSerializer.validate_tree') as validate_tree_mock:
            validate_tree_mock.side_effect = ValueError
            with self.assertRaises(serializers.ValidationError):
                pipeline_serializer.validate_plugin_id_tree(tree)
                validate_tree_mock.assert_called_with(tree_dict)

    def test_validate_tree(self):
        """
        Test whether custom validate_tree method raises ValueError if the passed
        dictionary represents a tree that is not connected.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        (plugin_ds1, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        (plugin_ds2, tf) = Plugin.objects.get_or_create(name="mri_analyze", type="ds",
                                                compute_resource=self.compute_resource)
        tree = [{"plugin_id": plugin_ds1.id, "child_indices": []},
                {"plugin_id": plugin_ds2.id, "child_indices": [2]},
                {"plugin_id": plugin_ds1.id, "child_indices": [1]}]
        tree_dict = {'root_index': 0, 'tree': tree}
        with self.assertRaises(ValueError):
            pipeline_serializer.validate_tree(tree_dict)

    def test_get_tree(self):
        """
        Test whether custom get_tree method creates a proper dictionary tree from
        a tree list.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        (plugin_ds1, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        (plugin_ds2, tf) = Plugin.objects.get_or_create(name="mri_analyze", type="ds",
                                                compute_resource=self.compute_resource)

        tree_list = [{"plugin_id": plugin_ds1.id, "previous_index": None},
                {"plugin_id": plugin_ds2.id, "previous_index": 0},
                {"plugin_id": plugin_ds1.id, "previous_index": 1}]

        tree = [{"plugin_id": plugin_ds1.id, "child_indices": [1]},
                {"plugin_id": plugin_ds2.id, "child_indices": [2]},
                {"plugin_id": plugin_ds1.id, "child_indices": []}]
        expected_tree_dict = {'root_index': 0, 'tree': tree}

        tree_dict = pipeline_serializer.get_tree(tree_list)
        self.assertEqual(tree_dict, expected_tree_dict)

    def test_get_tree_raises_value_error_if_no_root_found(self):
        """
        Test whether custom get_tree method raises ValueError if the passed tree list
        represents a tree with no root node.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        (plugin_ds1, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        (plugin_ds2, tf) = Plugin.objects.get_or_create(name="mri_analyze", type="ds",
                                                compute_resource=self.compute_resource)
        tree_list = [{"plugin_id": plugin_ds1.id, "previous_index": 0},
                {"plugin_id": plugin_ds2.id, "previous_index": 0},
                {"plugin_id": plugin_ds1.id, "previous_index": 1}]
        with self.assertRaises(ValueError):
            pipeline_serializer.get_tree(tree_list)

    def test_get_tree_raises_value_error_if_it_finds_invalid_previous_index(self):
        """
        Test whether custom get_tree method raises TypeError if the passed tree list
        has a node with None as previous index for a node that is not the root.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        (plugin_ds1, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        (plugin_ds2, tf) = Plugin.objects.get_or_create(name="mri_analyze", type="ds",
                                                compute_resource=self.compute_resource)

        tree_list = [{"plugin_id": plugin_ds1.id, "previous_index": None},
                {"plugin_id": plugin_ds2.id, "previous_index": 0},
                {"plugin_id": plugin_ds1.id, "previous_index": None}]
        with self.assertRaises(ValueError):
            pipeline_serializer.get_tree(tree_list)

        tree_list = [{"plugin_id": plugin_ds1.id, "previous_index": None},
                {"plugin_id": plugin_ds2.id, "previous_index": 3},
                {"plugin_id": plugin_ds1.id, "previous_index": 1}]
        with self.assertRaises(ValueError):
            pipeline_serializer.get_tree(tree_list)

    def test__add_plugin_tree_to_pipeline(self):
        """
        Test whether custom internal _add_plugin_tree_to_pipeline method properly
        associates a tree of plugins to a pipeline in the DB.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        (plugin_ds1, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        (plugin_ds2, tf) = Plugin.objects.get_or_create(name="mri_analyze", type="ds",
                                                compute_resource=self.compute_resource)

        tree = [{"plugin_id": plugin_ds1.id, "child_indices": [1]},
                {"plugin_id": plugin_ds2.id, "child_indices": [2]},
                {"plugin_id": plugin_ds1.id, "child_indices": []}]
        tree_dict = {'root_index': 0, 'tree': tree}

        pipeline_serializer._add_plugin_tree_to_pipeline(pipeline, tree_dict)
        pipeline_plg_names = [plugin.name for plugin in pipeline.plugins.all()]
        self.assertEqual(len(pipeline_plg_names), 3)
        self.assertEqual(len([name for name in pipeline_plg_names if name == "mri_convert"]), 2)
