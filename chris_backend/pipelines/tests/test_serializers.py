
import logging
from unittest import mock

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import serializers

from plugininstances.models import PluginInstance
from plugins.models import PluginMeta, Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultStrParameter, DefaultIntParameter
from pipelines.models import Pipeline
from pipelines.serializers import PipelineSerializer


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class SerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.plugin_fs_name = "simplefsapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': True,
                                             'default': "./"}}
        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'dummyInt': {'type': 'integer', 'optional': True,
                                                  'default': 111111}}
        self.plugin_ts_name = "ts_copy"

        self.username = 'foo'
        self.password = 'foo-pass'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create plugins
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_fs_name, type='fs')
        (plugin_fs, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_fs.compute_resources.set([self.compute_resource])
        plugin_fs.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ds_name, type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

        # add plugins' parameters
        (plg_param_fs, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])
        default = self.plugin_fs_parameters['dir']['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_fs,
                                                   value=default)  # set plugin parameter default

        # add a parameter with a default
        (plg_param_ds, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyInt',
            type=self.plugin_ds_parameters['dummyInt']['type'],
            optional=self.plugin_ds_parameters['dummyInt']['optional']
        )
        default = self.plugin_ds_parameters['dummyInt']['default']
        DefaultIntParameter.objects.get_or_create(plugin_param=plg_param_ds,
                                                  value=default)  # set plugin parameter default

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ts_name, type='ts')
        (plugin_ts, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ts.compute_resources.set([self.compute_resource])
        plugin_ts.save()

        # add a parameter with a default
        (plg_param_ts, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ts,
            name='plugininstances',
            type='string',
            optional=True
        )
        default = ""
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_ts,
                                                  value=default)  # set plugin parameter default

        # create user
        user = User.objects.create_user(username=self.username, password=self.password)

        # create a pipeline
        self.pipeline_name = 'Pipeline1'
        Pipeline.objects.get_or_create(name=self.pipeline_name, owner=user, category='test')

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class PipelineSerializerTests(SerializerTests):

    def setUp(self):
        super(PipelineSerializerTests, self).setUp()

    def test_create(self):
        """
        Test whether overriden 'create' method successfully creates a new pipeline
        with a tree of associated plugins.
        """
        plugin_ds1 = Plugin.objects.get(meta__name=self.plugin_ds_name)
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

        owner = User.objects.get(username=self.username)
        plugin_tree = '[{"title": "pip1", "plugin_id": ' + str(plugin_ds1.id) + \
                         ', "previous_index": null}, {"title": "pip2", "plugin_id": ' + \
                         str(plugin_ds2.id) + ', "previous_index": 0}]'
        data = {'name': 'Pipeline2', 'plugin_tree': plugin_tree}

        pipeline_serializer = PipelineSerializer(data=data)
        pipeline_serializer.is_valid(raise_exception=True)
        pipeline_serializer.validated_data['owner'] = owner
        pipeline = pipeline_serializer.create(pipeline_serializer.validated_data)
        pipeline_plg_names = [plugin.meta.name for plugin in pipeline.plugins.all()]
        self.assertIn(self.plugin_ds_name, pipeline_plg_names)
        self.assertIn("mri_analyze", pipeline_plg_names)

    def test_update(self):
        """
        Test whether overriden 'update' method successfully updates an existing pipeline
        even when 'validated_data' argument contains 'plugin_tree' and
        'plugin_inst_id'.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        validated_data = {'name': 'Pipeline2', 'plugin_tree': {'root_index': 0},
                          'plugin_inst_id': 1}
        pipeline_serializer.update(pipeline, validated_data)
        self.assertEqual(pipeline.name, 'Pipeline2')

    def test_validate_validates_required_fields_on_create(self):
        """
        Test whether overriden validate method validates that at least one of the fields
        'plugin_tree' or 'plugin_inst_id' must be provided when creating a new
        pipeline.
        """
        owner = User.objects.get(username=self.username)
        data = {'name': 'Pipeline2', 'owner': owner}
        pipeline_serializer = PipelineSerializer(data=data)
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate(data)

    def test_validate_validates_all_defaults_can_be_defined_if_pipeline_unlocked(self):
        """
        Test whether overriden validate method validates that all parameter defaults
        for the pipeline can be defined if the pipeline is unlocked.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        # add a parameter without a default
        PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyFloat',
            type='float',
            optional=False
        )
        owner = User.objects.get(username=self.username)
        plugin_tree = {'root_index': 0, 'tree': [{'plugin_id': plugin_ds.id,
                                                  'child_indices': [],
                                                  'plugin_parameter_defaults': []}]}
        data = {'name': 'Pipeline2', 'owner': owner, 'plugin_tree': plugin_tree, 'locked': False}
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
        plugin_fs = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (plugin_fs_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin_fs,
                                                                    owner=owner,
                                                compute_resource=self.compute_resource)
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_inst_id(plugin_fs_inst.id + 1)
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_inst_id(plugin_fs_inst.id)

    def test_validate_plugin_tree_is_json_string(self):
        """
        Test whether overriden validate_plugin_tree method validates that the plugin
        tree string is a proper JSON string.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        tree = '[{plugin_id: 8, "previous_index": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)

    def test_validate_plugin_tree_does_not_contain_empty_list(self):
        """
        Test whether overriden validate_plugin_tree method validates that the plugin
        tree is not an empty list.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        tree = '[]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)

    def test_validate_plugin_tree_plugins_exist_and_not_fs(self):
        """
        Test whether overriden validate_plugin_tree method validates that the plugin
        tree contains existing plugins that are not of type 'fs'.
        """
        plugin_fs = Plugin.objects.get(meta__name=self.plugin_fs_name)
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        tree = '[{"plugin_id": ' + str(plugin_fs.id + 100) + ', "previous_index": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)
        tree = '[{"plugin_id": ' + str(plugin_fs.id) + ', "previous_index": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)

    def test_validate_plugin_tree_raises_validation_error_if_get_tree_raises_value_error(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError if
        internal call to get_tree method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        tree = '[{"title": "pip7", "plugin_id": ' + str(plugin_ds.id) + ', "previous_index": null}]'
        with mock.patch('pipelines.serializers.PipelineSerializer.get_tree') as get_tree_mock:
            get_tree_mock.side_effect = ValueError
            with self.assertRaises(serializers.ValidationError):
                pipeline_serializer.validate_plugin_tree(tree)
            get_tree_mock.assert_called_with([{'title': 'pip7', 'plugin_id': plugin_ds.id,
                                               'previous_index': None,
                                               'plugin_parameter_defaults': []}])

    def test_validate_plugin_tree_raises_validation_error_if_validate_tree_raises_value_error(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError if
        internal call to validate_tree method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', "previous_index": null}]'
        tree_dict = {'root_index': 0, 'tree': [{"plugin_id": plugin_ds.id, "child_indices": []}]}
        with mock.patch('pipelines.serializers.PipelineSerializer.validate_tree') as validate_tree_mock:
            validate_tree_mock.side_effect = ValueError
            with self.assertRaises(serializers.ValidationError):
                pipeline_serializer.validate_plugin_tree(tree)
                validate_tree_mock.assert_called_with(tree_dict)

    def test_validate_plugin_tree_raises_validation_error_if_validate_DAG_raises_value_error(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError if
        internal call to validate_DAG method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        plugin_ts = Plugin.objects.get(meta__name=self.plugin_ts_name)
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', "previous_index": null, ' \
                '"title": "simpleds1"}, {"plugin_id": ' + str(plugin_ts.id) + '' \
                ', "previous_index": 0, "title": "topo1", "plugin_parameter_defaults": ' \
                '[{"name": "plugininstances", "default": "0,2"}]}]'
        with mock.patch('pipelines.serializers.PipelineSerializer.validate_DAG') as validate_DAG_mock:
            validate_DAG_mock.side_effect = ValueError
            with self.assertRaises(serializers.ValidationError):
                pipeline_serializer.validate_plugin_tree(tree)
                validate_DAG_mock.assert_called_with(tree, [False, True])

    def test_validate_plugin_tree_raises_validation_error_if_missing_a_tree_title(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError if
        internal call to validate_tree method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', previous_index": null}]'
        tree_dict = {'root_index': 0, 'tree': [{"plugin_id": plugin_ds.id, "child_indices": []}]}
        with mock.patch('pipelines.serializers.PipelineSerializer.validate_tree') as validate_tree_mock:
            validate_tree_mock.return_value = None
            with self.assertRaises(serializers.ValidationError):
                pipeline_serializer.validate_plugin_tree(tree)
                validate_tree_mock.assert_called_with(tree_dict)

    def test_validate_plugin_tree_raises_validation_error_if_duplicated_tree_title(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError if
        internal call to validate_tree method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        title = 20 * 's'
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', "title": ' + title + ', ' \
               'previous_index": null}, {"plugin_id": ' + str(plugin_ds.id) + ', ' \
               '"title": ' + title + ', previous_index": 0}]'
        with mock.patch('pipelines.serializers.PipelineSerializer.validate_tree') as validate_tree_mock:
            validate_tree_mock.return_value = None
            with self.assertRaises(serializers.ValidationError):
                pipeline_serializer.validate_plugin_tree(tree)

    def test_validate_plugin_tree_raises_validation_error_if_title_too_long(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError if
        internal call to validate_tree method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        title = 200 * 's'
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', "title": ' + title + ', previous_index": null}]'
        tree_dict = {'root_index': 0, 'tree': [{"plugin_id": plugin_ds.id, "title": title, "child_indices": []}]}
        with mock.patch('pipelines.serializers.PipelineSerializer.validate_tree') as validate_tree_mock:
            validate_tree_mock.return_value = None
            with self.assertRaises(serializers.ValidationError):
                pipeline_serializer.validate_plugin_tree(tree)
                validate_tree_mock.assert_called_with(tree_dict)

    def test_validate_plugin_parameter_defaults_raises_validation_error_if_missing_name_or_default(self):
        """
        Test whether custom validate_plugin_parameter_defaults method raises ValidationError if
        'name' or 'default' properties are not included.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        prev_ix = 0
        nplugin = 2
        parameter_defaults = [{'name': 'dummyInt'}]
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ds, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)
        parameter_defaults = [{'default': 3}]
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ds, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)
        parameter_defaults = [{'name': 'dummyInt', 'default': 3}]
        PipelineSerializer.validate_plugin_parameter_defaults(plugin_ds, prev_ix,
                                                              nplugin,
                                                              parameter_defaults)

    def test_validate_plugin_parameter_defaults_raises_validation_error_if_parameter_not_found(self):
        """
        Test whether custom validate_plugin_parameter_defaults method raises ValidationError if
        a parameter name is not found.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        prev_ix = 0
        nplugin = 2
        parameter_defaults = [{'name': 'randomInt', 'default': 3}]
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ds, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)

    def test_validate_plugin_parameter_defaults_raises_validation_error_if_invalid_default_value(self):
        """
        Test whether custom validate_plugin_parameter_defaults method raises ValidationError if
        an invalid default value is provided for a parameter.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        prev_ix = 0
        nplugin = 2
        parameter_defaults = [{'name': 'dummyInt', 'default': True}]
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ds, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)
    def test_validate_plugin_parameter_defaults_raises_validation_error_if_invalid_ts_default_value(self):
        """
        Test whether custom validate_plugin_parameter_defaults method raises ValidationError if
        an invalid default value is provided for the plugininstances parameter of a ts
        plugin.
        """
        plugin_ts = Plugin.objects.get(meta__name=self.plugin_ts_name)
        prev_ix = 0
        nplugin = 3

        parameter_defaults = [{'name': 'plugininstances', 'default': '0,a'}]  # list with non-ints
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)

        parameter_defaults = [{'name': 'plugininstances', 'default': '1'}]  # list doesn't include prev_ix
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)

        parameter_defaults = [{'name': 'plugininstances', 'default': ''}]  # empty list doesn't include prev_ix
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)

        parameter_defaults = [{'name': 'plugininstances', 'default': '0,3'}]  # list with out-of-range ints
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)
        prev_ix = None
        parameter_defaults = [{'name': 'plugininstances', 'default': '0'}]  # default must be the empty string
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_ix,
                                                                  nplugin,
                                                                  parameter_defaults)

    def test_validate_DAG_raises_value_error_if_cycle_found(self):
        """
        Test whether custom validate_DAG method raises ValueError if an indices cycle
        is found.
        """
        tree_list = [{'plugin_id': 4, 'previous_index': None, 'title': 'simpleds1',
          'plugin_parameter_defaults': []},
         {'plugin_id': 4, 'previous_index': 0, 'title': 'simpleds2',
          'plugin_parameter_defaults': []},
         {'plugin_id': 1, 'previous_index': 0, 'title': 'topo1',
          'plugin_parameter_defaults': [{'name': 'plugininstances', 'default': '0,2'}]}]

        plugin_is_ts_list = [False, False, True]

        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        with self.assertRaises(ValueError):
            pipeline_serializer.validate_DAG(tree_list, plugin_is_ts_list)

    def test_validate_DAG(self):
        """
        Test whether custom validate_DAG method properly validates a pipeline without
        cycles.
        """
        tree_list = [{'plugin_id': 4, 'previous_index': None, 'title': 'simpleds1',
          'plugin_parameter_defaults': []},
         {'plugin_id': 4, 'previous_index': 0, 'title': 'simpleds2',
          'plugin_parameter_defaults': []},
         {'plugin_id': 1, 'previous_index': 0, 'title': 'topo1',
          'plugin_parameter_defaults': [{'name': 'plugininstances', 'default': '0,1'}]}]

        plugin_is_ts_list = [False, False, True]

        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        result = pipeline_serializer.validate_DAG(tree_list, plugin_is_ts_list)
        self.assertIsNone(result)

    def test_validate_DAG_first_plugin_ts_and_empty_string_default(self):
        """
        Test whether custom validate_DAG method properly validates a pipeline without
        cycles where the first plugin is 'ts' and the default value of its
        plugininstances parameter is the empty string.
        """
        tree_list = [{'plugin_id': 1, 'previous_index': None, 'title': 'topo1',
                      'plugin_parameter_defaults': [{'name': 'plugininstances',
                                                     'default': ''}]},
                     {'plugin_id': 4, 'previous_index': 0, 'title': 'simpleds1',
                      'plugin_parameter_defaults': []}]

        plugin_is_ts_list = [True, False]

        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        result = pipeline_serializer.validate_DAG(tree_list, plugin_is_ts_list)
        self.assertIsNone(result)

    def test_get_tree(self):
        """
        Test whether custom get_tree method creates a proper dictionary tree from
        a tree list.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds1 = Plugin.objects.get(meta__name=self.plugin_ds_name)

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

        tree_list = [{"plugin_id": plugin_ds1.id,
                      "title": plugin_ds1.meta.name,
                      "plugin_parameter_defaults": [],
                      "previous_index": None},
                {"plugin_id": plugin_ds2.id,
                 "title": plugin_ds2.meta.name,
                 "plugin_parameter_defaults": [],
                 "previous_index": 0},
                {"plugin_id": plugin_ds1.id,
                 "title": "piping1",
                 "plugin_parameter_defaults": [],
                 "previous_index": 1}]

        tree = [{"plugin_id": plugin_ds1.id,
                 "title": plugin_ds1.meta.name,
                 "plugin_parameter_defaults": [],
                 "child_indices": [1]},
                {"plugin_id": plugin_ds2.id,
                 "title": plugin_ds2.meta.name,
                 "plugin_parameter_defaults": [],
                 "child_indices": [2]},
                {"plugin_id": plugin_ds1.id,
                 "title": "piping1",
                 "plugin_parameter_defaults": [],
                 "child_indices": []}]
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
        plugin_ds1 = Plugin.objects.get(meta__name=self.plugin_ds_name)

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

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
        plugin_ds1 = Plugin.objects.get(meta__name=self.plugin_ds_name)

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

        tree_list = [{"plugin_id": plugin_ds1.id,
                      "title": plugin_ds1.meta.name,
                      "plugin_parameter_defaults": [],
                      "previous_index": None},
                     {"plugin_id": plugin_ds2.id,
                      "title": plugin_ds2.meta.name,
                      "plugin_parameter_defaults": [],
                      "previous_index": 0},
                     {"plugin_id": plugin_ds1.id,
                      "title": "piping1",
                      "plugin_parameter_defaults": [],
                      "previous_index": None}]
        with self.assertRaises(ValueError):
            pipeline_serializer.get_tree(tree_list)

        tree_list = [{"plugin_id": plugin_ds1.id,
                      "title": plugin_ds1.meta.name,
                      "plugin_parameter_defaults": [],
                      "previous_index": None},
                     {"plugin_id": plugin_ds2.id,
                      "title": plugin_ds2.meta.name,
                      "plugin_parameter_defaults": [],
                      "previous_index": 3},
                     {"plugin_id": plugin_ds1.id,
                      "title": "piping1",
                      "plugin_parameter_defaults": [],
                      "previous_index": 1}]
        with self.assertRaises(ValueError):
            pipeline_serializer.get_tree(tree_list)

    def test_validate_tree(self):
        """
        Test whether custom validate_tree method raises ValueError if the passed
        dictionary represents a tree that is not connected.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds1 = Plugin.objects.get(meta__name=self.plugin_ds_name)

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

        tree = [{"plugin_id": plugin_ds1.id, "child_indices": []},
                {"plugin_id": plugin_ds2.id, "child_indices": [2]},
                {"plugin_id": plugin_ds1.id, "child_indices": [1]}]
        tree_dict = {'root_index': 0, 'tree': tree}
        with self.assertRaises(ValueError):
            pipeline_serializer.validate_tree(tree_dict)

    def test__add_plugin_tree_to_pipeline(self):
        """
        Test whether custom internal _add_plugin_tree_to_pipeline method properly
        associates a tree of plugins to a pipeline in the DB.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds1 = Plugin.objects.get(meta__name=self.plugin_ds_name)

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='ts_copy', type='ts')
        (plugin_ts, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ts.compute_resources.set([self.compute_resource])
        plugin_ts.save()
        # add a parameter with a default
        (plg_param_ts, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ts,
            name='plugininstances',
            type='string',
            optional=True
        )
        default = ""
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_ts,
                                                  value=default)  # set plugin parameter default

        tree = [{"plugin_id": plugin_ds1.id,
                 "title": plugin_ds1.meta.name,
                 "plugin_parameter_defaults": [],
                 "child_indices": [1]},
                {"plugin_id": plugin_ds2.id,
                 "title": "piping2",
                 "plugin_parameter_defaults": [],
                 "child_indices": [2]},
                {"plugin_id": plugin_ds1.id,
                 "title": "piping1",
                 "plugin_parameter_defaults": [],
                 "child_indices": [3]},
                {"plugin_id": plugin_ts.id,
                 "title": "piping3",
                 "plugin_parameter_defaults": [{'name': 'plugininstances', 'default': '1,2'}],
                 "child_indices": [4]},
                {"plugin_id": plugin_ds1.id,
                 "title": "piping4",
                 "plugin_parameter_defaults": [],
                 "child_indices": []},
                ]
        tree_dict = {'root_index': 0, 'tree': tree}

        pipeline_serializer._add_plugin_tree_to_pipeline(pipeline, tree_dict)
        pipeline_plg_names = [plugin.meta.name for plugin in pipeline.plugins.all()]
        self.assertEqual(len(pipeline_plg_names), 5)
        self.assertEqual(len([name for name in pipeline_plg_names if name ==
                              self.plugin_ds_name]), 3)
        self.assertEqual(1, pipeline.plugins.filter(meta__type='ts').count())

        plg_pip_ids = [pip.id for pip in pipeline.plugin_pipings.all()]
        ts_pip = pipeline.plugin_pipings.filter(plugin__meta__type='ts').first()
        param = ts_pip.string_param.filter(plugin_param__name='plugininstances').first()
        parent_ixs = [int(parent_ix) for parent_ix in param.value.split(',')]
        for ix in parent_ixs:
            self.assertIn(ix, plg_pip_ids)
