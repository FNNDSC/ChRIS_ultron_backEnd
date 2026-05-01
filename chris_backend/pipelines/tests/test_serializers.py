
import logging
import io
import json
from unittest import mock

import yaml

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import serializers

from plugininstances.models import PluginInstance
from plugins.models import PluginMeta, Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultStrParameter, DefaultIntParameter
from pipelines.models import Pipeline, PluginPiping
from pipelines.serializers import (PipelineSerializer, PipelineSourceFileSerializer, 
                                   PluginPipingSerializer)


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL
CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class SerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

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
                         ', "previous": null}, {"title": "pip2", "plugin_id": ' + \
                         str(plugin_ds2.id) + ', "previous": "pip1"}]'
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

    def test_validate_name(self):
        """
        Test whether overriden validate_name method raises a serializers.ValidationError
        when a pipeline with the provided name already exists in the DB, and returns the
        name unchanged when it is unique.
        """
        pipeline_serializer = PipelineSerializer(data={})
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_name(self.pipeline_name)
        self.assertEqual(pipeline_serializer.validate_name('UniquePipelineName'),
                         'UniquePipelineName')

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
        tree = '[{plugin_id: 8, "previous": null}]'
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
        tree = '[{"plugin_id": ' + str(plugin_fs.id + 100) + ', "previous": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)
        tree = '[{"plugin_id": ' + str(plugin_fs.id) + ', "previous": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)

    def test_validate_plugin_tree_raises_validation_error_if_invalid_previous_found(self):
        """
        Test whether overriden validate_plugin_tree method raises serializers.ValidationError
        if the passed tree list has a node with None as previous for a node that is not the root.
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
                      "previous": None},
                     {"plugin_id": plugin_ds2.id,
                      "title": plugin_ds2.meta.name,
                      "previous": plugin_ds1.meta.name},
                     {"plugin_id": plugin_ds1.id,
                      "title": "piping1",
                      "previous": None}]
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree_list)

        tree_list = [{"plugin_id": plugin_ds1.id,
                      "title": plugin_ds1.meta.name,
                      "previous": None},
                     {"plugin_id": plugin_ds2.id,
                      "title": plugin_ds2.meta.name,
                      "previous": "unknowntitle"},
                     {"plugin_id": plugin_ds1.id,
                      "title": "piping1",
                      "previous": plugin_ds2.id}]
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree_list)

    def test_validate_plugin_tree_raises_validation_error_if_no_root_found(self):
        """
        Test whether overriden validate_plugin_tree method raises serializers.ValidationError
        if the passed tree list represents a tree with no root node.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds1 = Plugin.objects.get(meta__name=self.plugin_ds_name)

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

        tree_list = [{"plugin_id": plugin_ds1.id, "previous": "plugin0", "title": "plugin0"},
                {"plugin_id": plugin_ds2.id, "previous": "plugin0", "title": "plugin1"},
                {"plugin_id": plugin_ds1.id, "previous": "plugin1", "title": "plugin2"}]
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree_list)

    def test_validate_plugin_tree_raises_validation_error_if_missing_a_tree_title(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError if
        internal call to validate_tree method raises ValueError exception.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', previous": null}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)

    def test_validate_plugin_tree_raises_validation_error_if_duplicated_tree_title(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError if
        duplicated title is found.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        title = 20 * 's'
        tree = '[{"plugin_id": ' + str(plugin_ds.id) + ', "title": ' + title + ', ' \
               'previous": null}, {"plugin_id": ' + str(plugin_ds.id) + ', ' \
               '"title": ' + title + ', previous": ' + title + '}]'
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)

    def test_validate_plugin_tree_raises_validation_error_if_title_too_long(self):
        """
        Test whether overriden validate_plugin_tree method raises ValidationError when
        a node's title exceeds the model's max_length=100. The check is performed by
        PluginPipingSerializer's auto-generated title field.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        long_title = 200 * 's'
        tree = json.dumps([{'plugin_id': plugin_ds.id, 'title': long_title,
                            'previous': None}])
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_plugin_tree(tree)

    def test_validate_plugin_tree_error_message_reports_failing_node_title(self):
        """
        Regression test: when a non-last node fails per-node validation (e.g. its
        cpu_limit is below the plugin's min_cpu_limit), the raised ValidationError
        must reference that node's title, not the title of the last node in the tree.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        below_min_cpu = plugin_ds.min_cpu_limit - 1
        failing_title = 'first-node'
        last_title = 'last-node-different'
        tree = json.dumps([
            {'plugin_id': plugin_ds.id, 'title': failing_title, 'previous': None,
             'cpu_limit': below_min_cpu},
            {'plugin_id': plugin_ds.id, 'title': last_title, 'previous': failing_title},
        ])

        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        with self.assertRaises(serializers.ValidationError) as ctx:
            pipeline_serializer.validate_plugin_tree(tree)

        msg = str(ctx.exception.detail)
        self.assertIn(failing_title, msg)
        self.assertNotIn(last_title, msg)

    def test_validate_plugin_parameter_defaults_raises_validation_error_if_missing_default(self):
        """
        Test whether custom validate_plugin_parameter_defaults method raises ValidationError if
        'name' or 'default' properties are not included.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        title_to_ix = {'plugin0': 0, 'plugin1': 1}
        prev_title = 'plugin0'
        parameter_defaults = [{'name': 'dummyInt'}]
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ds, prev_title,
                                                                  title_to_ix,
                                                                  parameter_defaults)
        parameter_defaults = [{'name': 'dummyInt', 'default': 3}]
        PipelineSerializer.validate_plugin_parameter_defaults(plugin_ds, prev_title,
                                                              title_to_ix,
                                                              parameter_defaults)

    def test_validate_plugin_parameter_defaults_validates_all_defaults_can_be_defined(self):
        """
        Test whether custom validate_plugin_parameter_defaults method validates that all
        parameter defaults for the pipeline can be defined.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        # add a parameter without a default
        PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyFloat',
            type='float',
            optional=False
        )
        title_to_ix = {'plugin0': 0}
        prev_title = None
        parameter_defaults = []
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ds, prev_title,
                                                                  title_to_ix,
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
        title_to_ix = {'plugin0': 0, 'plugin1': 1, 'plugin2': 2}
        prev_title = 'plugin0'

        parameter_defaults = [{'name': 'plugininstances', 'default': 'plugin1'}]  # list doesn't include prev_title
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_title,
                                                                  title_to_ix,
                                                                  parameter_defaults)

        parameter_defaults = [{'name': 'plugininstances', 'default': ''}]  # empty list doesn't include prev_title
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_title,
                                                                  title_to_ix,
                                                                  parameter_defaults)

        parameter_defaults = [{'name': 'plugininstances', 'default': 'plugin0,unknowntitle'}]  # list with unknown titles
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_title,
                                                                  title_to_ix,
                                                                  parameter_defaults)
        prev_title = None
        parameter_defaults = [{'name': 'plugininstances', 'default': 'plugin0'}]  # default must be the empty string
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer.validate_plugin_parameter_defaults(plugin_ts, prev_title,
                                                                  title_to_ix,
                                                                  parameter_defaults)

    def test_validate_DAG_raises_validation_error_if_cycle_found(self):
        """
        Test whether custom validate_DAG method raises serializers.ValidationError if an
        indices cycle is found.
        """
        tree_list = [{'plugin_id': 4, 'previous': None, 'title': 'simpleds1',
          'plugin_parameter_defaults': []},
         {'plugin_id': 4, 'previous': 0, 'title': 'simpleds2',
          'plugin_parameter_defaults': []},
         {'plugin_id': 1, 'previous': 0, 'title': 'topo1',
          'plugin_parameter_defaults': [{'name': 'plugininstances', 'default': '0,2'}]}]

        plugin_is_ts_list = [False, False, True]

        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        with self.assertRaises(serializers.ValidationError):
            pipeline_serializer.validate_DAG(tree_list, plugin_is_ts_list)

    def test_validate_DAG(self):
        """
        Test whether custom validate_DAG method properly validates a pipeline without
        cycles.
        """
        tree_list = [{'plugin_id': 4, 'previous': None, 'title': 'simpleds1',
          'plugin_parameter_defaults': []},
         {'plugin_id': 4, 'previous': 0, 'title': 'simpleds2',
          'plugin_parameter_defaults': []},
         {'plugin_id': 1, 'previous': 0, 'title': 'topo1',
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
        tree_list = [{'plugin_id': 1, 'previous': None, 'title': 'topo1',
                      'plugin_parameter_defaults': [{'name': 'plugininstances',
                                                     'default': ''}]},
                     {'plugin_id': 4, 'previous': 0, 'title': 'simpleds1',
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
                      "previous": None},
                {"plugin_id": plugin_ds2.id,
                 "title": plugin_ds2.meta.name,
                 "plugin_parameter_defaults": [],
                 "previous": 0},
                {"plugin_id": plugin_ds1.id,
                 "title": "piping1",
                 "plugin_parameter_defaults": [],
                 "previous": 1}]

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

    def test_get_tree_propagates_per_node_resource_fields(self):
        """
        Regression test: get_tree must carry per-node resource overrides
        (cpu_limit, memory_limit, number_of_workers, gpu_limit) into the canonical
        tree nodes, and only when present on the input node. Without this, the
        resource values declared in a YAML/JSON pipeline source file silently fail
        to propagate to the created PluginPiping rows.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)

        tree_list = [
            {'plugin_id': plugin_ds.id, 'title': 'root',
             'plugin_parameter_defaults': [], 'previous': None,
             'cpu_limit': '2500m', 'memory_limit': '512Mi',
             'number_of_workers': 2, 'gpu_limit': 1},
            {'plugin_id': plugin_ds.id, 'title': 'child',
             'plugin_parameter_defaults': [], 'previous': 0},
        ]
        tree_dict = pipeline_serializer.get_tree(tree_list)

        root = tree_dict['tree'][tree_dict['root_index']]
        self.assertEqual(root['cpu_limit'], '2500m')
        self.assertEqual(root['memory_limit'], '512Mi')
        self.assertEqual(root['number_of_workers'], 2)
        self.assertEqual(root['gpu_limit'], 1)

        child = tree_dict['tree'][1]
        for f in ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit'):
            self.assertNotIn(f, child)

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

    def test__parse_plugin_tree_invalid_json(self):
        """
        Test that _parse_plugin_tree raises ValidationError for non-JSON input.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._parse_plugin_tree('not-a-json')

    def test__parse_plugin_tree_empty_list(self):
        """
        Test that _parse_plugin_tree raises ValidationError for an empty list.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._parse_plugin_tree('[]')

    def test__parse_plugin_tree_returns_list(self):
        """
        Test that _parse_plugin_tree returns the parsed list for valid input.
        """
        result = PipelineSerializer._parse_plugin_tree(
            '[{"title": "a", "previous": null}]')
        self.assertEqual(result, [{'title': 'a', 'previous': None}])

    def test__build_title_to_ix_happy_path(self):
        """
        Test that _build_title_to_ix returns the title-to-index mapping.
        """
        plugin_list = [{'title': 'a'}, {'title': 'b'}, {'title': 'c'}]
        self.assertEqual(PipelineSerializer._build_title_to_ix(plugin_list),
                         {'a': 0, 'b': 1, 'c': 2})

    def test__build_title_to_ix_missing_title_raises(self):
        """
        Test that _build_title_to_ix raises ValidationError when a node is
        missing its title.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._build_title_to_ix([{'title': 'a'}, {}])

    def test__build_title_to_ix_duplicate_title_raises(self):
        """
        Test that _build_title_to_ix raises ValidationError on duplicated titles.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._build_title_to_ix(
                [{'title': 'a'}, {'title': 'a'}])

    def test__validate_node_plugin_resolves_plugin_id(self):
        """
        Test that _validate_node_plugin resolves plugin_id, sets found_root_node
        on the root, and returns (plugin, prev_title, found_root_node).
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'title': 'a', 'plugin_id': plugin_ds.id, 'previous': None}
        plg, prev, found = PipelineSerializer._validate_node_plugin(d, {'a': 0}, False)
        self.assertEqual(plg.id, plugin_ds.id)
        self.assertIsNone(prev)
        self.assertTrue(found)

    def test__validate_node_plugin_resolves_plugin_name_and_version(self):
        """
        Test that _validate_node_plugin resolves a node by plugin_name +
        plugin_version when plugin_id is absent and assigns plugin_id back to d.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'title': 'a', 'plugin_name': self.plugin_ds_name,
             'plugin_version': '0.1', 'previous': None}
        plg, _, _ = PipelineSerializer._validate_node_plugin(d, {'a': 0}, False)
        self.assertEqual(plg.id, plugin_ds.id)
        self.assertEqual(d['plugin_id'], plugin_ds.id)

    def test__validate_node_plugin_rejects_fs_plugin(self):
        """
        Test that _validate_node_plugin raises ValidationError when the resolved
        plugin is of type 'fs'.
        """
        plugin_fs = Plugin.objects.get(meta__name=self.plugin_fs_name)
        d = {'title': 'a', 'plugin_id': plugin_fs.id, 'previous': None}
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_node_plugin(d, {'a': 0}, False)

    def test__validate_node_plugin_rejects_unknown_plugin_id(self):
        """
        Test that _validate_node_plugin raises ValidationError when no plugin
        with the supplied plugin_id exists.
        """
        d = {'title': 'a', 'plugin_id': 999999, 'previous': None}
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_node_plugin(d, {'a': 0}, False)

    def test__validate_node_plugin_rejects_unknown_previous(self):
        """
        Test that _validate_node_plugin raises ValidationError when the previous
        title is not in title_to_ix.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'title': 'b', 'plugin_id': plugin_ds.id, 'previous': 'unknown'}
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_node_plugin(d, {'b': 0}, False)

    def test__validate_node_plugin_rejects_disconnected_tree(self):
        """
        Test that _validate_node_plugin raises ValidationError when a second
        root (previous=None) is encountered.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'title': 'b', 'plugin_id': plugin_ds.id, 'previous': None}
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_node_plugin(d, {'b': 0}, True)

    def test__validate_previous_pointer_root_marks_found(self):
        """
        Test that _validate_previous_pointer returns True when prev_title is
        None and no root has been seen yet.
        """
        self.assertTrue(
            PipelineSerializer._validate_previous_pointer(None, {}, False))

    def test__validate_previous_pointer_second_root_raises(self):
        """
        Test that _validate_previous_pointer raises ValidationError when a
        second root (None previous) is encountered.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_previous_pointer(None, {}, True)

    def test__validate_previous_pointer_unknown_title_raises(self):
        """
        Test that _validate_previous_pointer raises ValidationError when
        prev_title is not in title_to_ix.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_previous_pointer('unknown', {'a': 0},
                                                          False)

    def test__validate_previous_pointer_known_title_passthrough(self):
        """
        Test that _validate_previous_pointer returns found_root_node unchanged
        when prev_title is known.
        """
        self.assertTrue(
            PipelineSerializer._validate_previous_pointer('a', {'a': 0}, True))

    def test__resolve_node_plugin_by_id(self):
        """
        Test that _resolve_node_plugin resolves the Plugin by plugin_id.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'plugin_id': plugin_ds.id}
        plg = PipelineSerializer._resolve_node_plugin(d)
        self.assertEqual(plg.id, plugin_ds.id)

    def test__resolve_node_plugin_by_name_and_version(self):
        """
        Test that _resolve_node_plugin resolves the Plugin by plugin_name and
        plugin_version, and back-fills d['plugin_id'].
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'plugin_name': self.plugin_ds_name, 'plugin_version': '0.1'}
        plg = PipelineSerializer._resolve_node_plugin(d)
        self.assertEqual(plg.id, plugin_ds.id)
        self.assertEqual(d['plugin_id'], plugin_ds.id)

    def test__resolve_node_plugin_malformed_raises(self):
        """
        Test that _resolve_node_plugin raises ValidationError when neither
        plugin_id nor plugin_name+plugin_version are present.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._resolve_node_plugin({})

    def test__resolve_node_plugin_unknown_id_raises(self):
        """
        Test that _resolve_node_plugin raises ValidationError when plugin_id
        does not match any plugin in the DB.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._resolve_node_plugin({'plugin_id': 99999})

    def test__validate_node_resources_happy_path(self):
        """
        Test that _validate_node_resources accepts in-range per-piping resources.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'title': 'a', 'cpu_limit': plugin_ds.min_cpu_limit}
        # should not raise
        PipelineSerializer._validate_node_resources(plugin_ds, d)

    def test__validate_node_resources_includes_node_title_in_error(self):
        """
        Test that _validate_node_resources raises ValidationError mentioning
        the offending node's title when a resource value is out of range.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'title': 'failing-node', 'cpu_limit': plugin_ds.min_cpu_limit - 1}
        with self.assertRaises(serializers.ValidationError) as ctx:
            PipelineSerializer._validate_node_resources(plugin_ds, d)
        self.assertIn('failing-node', str(ctx.exception.detail))

    def test__normalize_node_parameter_defaults_installs_empty_list(self):
        """
        Test that _normalize_node_parameter_defaults installs an empty
        plugin_parameter_defaults list when the key is missing.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        d = {'title': 'a'}
        PipelineSerializer._normalize_node_parameter_defaults(d, plugin_ds, None,
                                                              {'a': 0})
        self.assertEqual(d['plugin_parameter_defaults'], [])

    def test__normalize_node_parameter_defaults_maps_ts_titles_to_indices(self):
        """
        Test that _normalize_node_parameter_defaults rewrites the
        'plugininstances' default for 'ts' plugins from comma-separated titles
        to comma-separated indices.
        """
        plugin_ts = Plugin.objects.get(meta__name=self.plugin_ts_name)
        d = {'title': 'b',
             'plugin_parameter_defaults':
                 [{'name': 'plugininstances', 'default': 'a,b'}]}
        title_to_ix = {'a': 0, 'b': 1}
        PipelineSerializer._normalize_node_parameter_defaults(
            d, plugin_ts, 'a', title_to_ix)
        self.assertEqual(d['plugin_parameter_defaults'][0]['default'], '0,1')

    def test__validate_user_default_invalid_value_type_raises(self):
        """
        Test that _validate_user_default raises ValidationError when a default
        value cannot be parsed by the typed DEFAULT_PARAMETER_SERIALIZERS.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        param = plugin_ds.parameters.get(name='dummyInt')
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_user_default(
                plugin_ds, None, {}, param,
                {'name': 'dummyInt', 'default': 'not-an-int'})

    def test__validate_user_default_missing_default_key_raises(self):
        """
        Test that _validate_user_default raises ValidationError when the entry
        is missing the 'default' key.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        param = plugin_ds.parameters.get(name='dummyInt')
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_user_default(
                plugin_ds, None, {}, param, {'name': 'dummyInt'})

    def test__validate_user_default_happy_path(self):
        """
        Test that _validate_user_default accepts a well-formed entry.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        param = plugin_ds.parameters.get(name='dummyInt')
        # should not raise
        PipelineSerializer._validate_user_default(
            plugin_ds, None, {}, param, {'name': 'dummyInt', 'default': 7})

    def test__validate_ts_plugininstances_default_null_previous_with_default_raises(self):
        """
        Test that _validate_ts_plugininstances_default raises ValidationError
        when previous_title is None but a default is provided.
        """
        plugin_ts = Plugin.objects.get(meta__name=self.plugin_ts_name)
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_ts_plugininstances_default(
                plugin_ts, None, {'a': 0}, 'a')

    def test__validate_ts_plugininstances_default_set_previous_with_empty_default_raises(self):
        """
        Test that _validate_ts_plugininstances_default raises ValidationError
        when previous_title is set but default is empty.
        """
        plugin_ts = Plugin.objects.get(meta__name=self.plugin_ts_name)
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._validate_ts_plugininstances_default(
                plugin_ts, 'a', {'a': 0}, '')

    def test__validate_ts_plugininstances_default_happy_path(self):
        """
        Test that _validate_ts_plugininstances_default accepts a list that
        contains the previous title and only known titles.
        """
        plugin_ts = Plugin.objects.get(meta__name=self.plugin_ts_name)
        # should not raise
        PipelineSerializer._validate_ts_plugininstances_default(
            plugin_ts, 'a', {'a': 0, 'b': 1}, 'a,b')

    def test__resolve_instance_tree_ts_indices_rewrites_ids(self):
        """
        Test that _resolve_instance_tree_ts_indices rewrites
        'plugininstances' from instance ids to tree indices and flattens
        plugin_id from the Plugin object to its primary key.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        plugin_ts = Plugin.objects.get(meta__name=self.plugin_ts_name)
        tree_dict = {'root_index': 0, 'tree': [
            {'plugin_id': plugin_ds, 'plugin_parameter_defaults': [],
             'child_indices': [1]},
            {'plugin_id': plugin_ts,
             'plugin_parameter_defaults':
                 [{'name': 'plugininstances', 'default': '100,200'}],
             'child_indices': []},
        ]}
        inst_id_to_ix = {100: 0, 200: 1}
        PipelineSerializer._resolve_instance_tree_ts_indices(tree_dict,
                                                             inst_id_to_ix)
        self.assertEqual(tree_dict['tree'][0]['plugin_id'], plugin_ds.id)
        self.assertEqual(tree_dict['tree'][1]['plugin_id'], plugin_ts.id)
        self.assertEqual(
            tree_dict['tree'][1]['plugin_parameter_defaults'][0]['default'],
            '0,1')

    def test__collect_tree_from_instance_duplicate_titles_raises(self):
        """
        Test that _collect_tree_from_instance raises ValidationError when two
        visited plugin instances share the same title.
        """
        plugin_fs = Plugin.objects.get(meta__name=self.plugin_fs_name)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        owner = User.objects.get(username=self.username)
        root, _ = PluginInstance.objects.get_or_create(
            plugin=plugin_fs, owner=owner, title='dup',
            compute_resource=self.compute_resource)
        PluginInstance.objects.get_or_create(
            plugin=plugin_ds, owner=owner, title='dup', previous=root,
            compute_resource=self.compute_resource)
        with self.assertRaises(serializers.ValidationError):
            PipelineSerializer._collect_tree_from_instance(root)

    def test__create_piping_persists_plugin_piping(self):
        """
        Test that _create_piping creates a PluginPiping row with the requested
        title, plugin and previous, and returns it.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        node = {'plugin_id': plugin_ds.id, 'title': 'fresh-piping',
                'plugin_parameter_defaults': []}
        piping = PipelineSerializer._create_piping(pipeline, node, None)
        self.assertEqual(piping.title, 'fresh-piping')
        self.assertEqual(piping.plugin.id, plugin_ds.id)
        self.assertIsNone(piping.previous)
        self.assertEqual(
            PluginPiping.objects.filter(pipeline=pipeline,
                                        title='fresh-piping').count(),
            1)

    def test__create_pipings_bfs_creates_all_pipings(self):
        """
        Test that _create_pipings_bfs creates one PluginPiping per tree node and
        returns the index-to-piping dict in BFS order.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        tree_dict = {'root_index': 0, 'tree': [
            {'plugin_id': plugin_ds.id, 'title': 'r',
             'plugin_parameter_defaults': [], 'child_indices': [1, 2]},
            {'plugin_id': plugin_ds.id, 'title': 'c1',
             'plugin_parameter_defaults': [], 'child_indices': []},
            {'plugin_id': plugin_ds.id, 'title': 'c2',
             'plugin_parameter_defaults': [], 'child_indices': []},
        ]}
        plg_pipings_dict = PipelineSerializer._create_pipings_bfs(pipeline,
                                                                  tree_dict)
        self.assertEqual(set(plg_pipings_dict.keys()), {0, 1, 2})
        self.assertEqual(plg_pipings_dict[0].title, 'r')
        self.assertEqual(plg_pipings_dict[1].previous, plg_pipings_dict[0])
        self.assertEqual(plg_pipings_dict[2].previous, plg_pipings_dict[0])

    def test__finalize_ts_pipings_rewrites_indices_to_piping_ids(self):
        """
        Test that _finalize_ts_pipings rewrites the 'plugininstances' default
        from comma-separated tree indices to comma-separated piping ids for ts
        pipings.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        plugin_ts = Plugin.objects.get(meta__name=self.plugin_ts_name)
        tree_dict = {'root_index': 0, 'tree': [
            {'plugin_id': plugin_ds.id, 'title': 'r',
             'plugin_parameter_defaults': [], 'child_indices': [1]},
            {'plugin_id': plugin_ts.id, 'title': 't',
             'plugin_parameter_defaults':
                 [{'name': 'plugininstances', 'default': '0'}],
             'child_indices': []},
        ]}
        plg_pipings_dict = PipelineSerializer._create_pipings_bfs(pipeline,
                                                                  tree_dict)
        PipelineSerializer._finalize_ts_pipings(plg_pipings_dict)
        ts_param = plg_pipings_dict[1].string_param.filter(
            plugin_param__name='plugininstances').first()
        self.assertEqual(ts_param.value, str(plg_pipings_dict[0].id))

    def test__add_plugin_tree_to_pipeline_normalizes_string_resource_limits(self):
        """
        Regression test: when a tree node carries cpu_limit/memory_limit as
        Kubernetes-style strings (the YAML/JSON pipeline source path), the created
        PluginPiping must persist them as the equivalent integer values rather than
        crashing in CPUField.get_prep_value with int('NNNm').
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pipeline_serializer = PipelineSerializer(pipeline)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)

        tree_dict = {
            'root_index': 0,
            'tree': [
                {'plugin_id': plugin_ds.id, 'title': 'root',
                 'plugin_parameter_defaults': [], 'child_indices': [1],
                 'cpu_limit': '2500m', 'memory_limit': '2Gi',
                 'number_of_workers': 3, 'gpu_limit': 1},
                {'plugin_id': plugin_ds.id, 'title': 'child',
                 'plugin_parameter_defaults': [], 'child_indices': []},
            ],
        }

        pipeline_serializer._add_plugin_tree_to_pipeline(pipeline, tree_dict)

        root = pipeline.plugin_pipings.get(title='root')
        self.assertEqual(int(root.cpu_limit), 2500)
        self.assertEqual(int(root.memory_limit), 2048)
        self.assertEqual(root.number_of_workers, 3)
        self.assertEqual(root.gpu_limit, 1)


class PipelineSourceFileSerializerTests(SerializerTests):

    def setUp(self):
        super(PipelineSourceFileSerializerTests, self).setUp()
        self.yaml_pipeline_str = """
        name: TestPipeline
        locked: false
        plugin_tree:
        - title: simpledsapp1
          plugin: simpledsapp v0.1
          previous: ~
        - title: simpledsapp2
          plugin: simpledsapp v0.1
          previous: simpledsapp1
        - title: join
          plugin: ts_copy v0.1
          previous: simpledsapp1
          plugin_parameter_defaults:
            plugininstances: simpledsapp1,simpledsapp2
        """
        self.json_pipeline_str = '{"name": "TestPipeline", "locked": false,' \
                                 '"plugin_tree": [' \
                                 '{"title": "simpledsapp1",' \
                                 '"plugin_name": "simpledsapp", ' \
                                 '"plugin_version": "0.1","previous": null},' \
                                 '{"title": "simpledsapp2",' \
                                 '"plugin_name": "simpledsapp",' \
                                 '"plugin_version": "0.1","previous": "simpledsapp1"},' \
                                 '{"title": "join",' \
                                 '"plugin_name": "ts_copy",' \
                                 '"plugin_version": "0.1","previous": "simpledsapp1",' \
                                 '"plugin_parameter_defaults": [' \
                                 '{"name": "plugininstances",' \
                                 '"default": "simpledsapp1,simpledsapp2"}]}]}'

    def test_validate_fname(self):
        """
        Test whether overriden validate_fname method validates that a file
        name does not only contain commas and white spaces.
        """
        pipeline_file_serializer = PipelineSourceFileSerializer()
        fname = mock.Mock()
        fname.name = 'User/path/, ,'

        with self.assertRaises(serializers.ValidationError):
            pipeline_file_serializer.validate_fname(fname)

    def test_read_yaml_pipeline_representation(self):
        """
        Test whether custom read_yaml_pipeline_representation method returns an appropriate
        yaml pipeline representation from an uploaded yaml representation file.
        """
        pipeline_repr = yaml.safe_load(self.yaml_pipeline_str)
        with io.BytesIO(self.yaml_pipeline_str.encode()) as f:
            self.assertEqual(PipelineSourceFileSerializer.read_yaml_pipeline_representation(f),
                             pipeline_repr)

    def test_read_yaml_pipeline_representation_raises_validation_error_if_invalid_yaml_file(self):
        """
        Test whether custom read_yaml_pipeline_representation method raises ValidationError if
        uploaded yaml representation file is invalid.
        """
        pipeline_str = """
        name: TestPipeline
        locked: false
        plugin_tree:
        - title: simpledsapp1
          plugin: simpledsapp v0.1
          previous: ~
          - title: simpledsapp2
          plugin: simpledsapp v0.1
          previous: simpledsapp1
        """
        with self.assertRaises(serializers.ValidationError):
            with io.BytesIO(pipeline_str.encode()) as f:
                PipelineSourceFileSerializer.read_yaml_pipeline_representation(f)

    def test_read_json_pipeline_representation(self):
        """
        Test whether custom read_json_pipeline_representation method returns an appropriate
        json pipeline representation from an uploaded json representation file.
        """
        pipeline_repr = json.loads(self.json_pipeline_str)
        with io.BytesIO(self.json_pipeline_str.encode()) as f:
            self.assertEqual(PipelineSourceFileSerializer.read_json_pipeline_representation(f),
                             pipeline_repr)

    def test_read_json_pipeline_representation_raises_validation_error_if_invalid_json_file(self):
        """
        Test whether custom read_json_pipeline_representation method raises
        ValidationError if uploaded json representation file is invalid.
        """
        pipeline_str = '{"name": "TestPipeline", "locked": false,' \
                         '"plugin_tree": [' \
                         '{"title": "simpledsapp1",' \
                         '"plugin_name": "simpledsapp", ' \
                         '"plugin_version": "0.1","previous": null},' \
                         '{"title": "simpledsapp2",' \
                         '"plugin_name": "simpledsapp",' \
                         '"plugin_version": "0.1","previous": "simpledsapp1"}}'
        with self.assertRaises(serializers.ValidationError):
            with io.BytesIO(pipeline_str.encode()) as f:
                PipelineSourceFileSerializer.read_json_pipeline_representation(f)

    def test_get_yaml_pipeline_canonical_representation(self):
        """
        Test whether custom get_yaml_pipeline_canonical_representation method returns an
        appropriate canonical JSON pipeline representation from the yaml representation.
        """
        pipeline_repr = yaml.safe_load(self.yaml_pipeline_str)
        canonical_repr = {'name': 'TestPipeline',
                          'locked': False,
                          'plugin_tree': '[{"title": "simpledsapp1", "plugin_name": "simpledsapp", "plugin_version": "0.1", "previous": null}, '
                                         '{"title": "simpledsapp2", "plugin_name": "simpledsapp", "plugin_version": "0.1", "previous": "simpledsapp1"}, '
                                         '{"title": "join", "plugin_name": "ts_copy", "plugin_version": "0.1", "previous": "simpledsapp1", '
                                         '"plugin_parameter_defaults": [{"name": "plugininstances", "default": "simpledsapp1,simpledsapp2"}]}]'}
        self.assertEqual(PipelineSourceFileSerializer.get_yaml_pipeline_canonical_representation(pipeline_repr),
                         canonical_repr)


    def test_get_yaml_pipeline_canonical_representation_raises_validation_error_if_missing_node_plugin(self):
        """
        Test whether custom get_yaml_pipeline_canonical_representation method raises
        ValidationError if a node is missing its plugin.
        """
        pipeline_str = """
        name: TestPipeline
        locked: false
        plugin_tree:
        - title: simpledsapp1
          previous: ~
        """
        pipeline_repr = yaml.safe_load(pipeline_str)
        with self.assertRaises(serializers.ValidationError):
            PipelineSourceFileSerializer.get_yaml_pipeline_canonical_representation(pipeline_repr)

    def test_get_yaml_pipeline_canonical_representation_raises_validation_error_if_missing_plugin_name_or_version(self):
        """
        Test whether custom get_yaml_pipeline_canonical_representation method raises
        ValidationError if a node is missing its plugin name or version.
        """
        pipeline_str = """
        name: TestPipeline
        locked: false
        plugin_tree:
        - title: simpledsapp1
          plugin: simpledsapp 
          previous: ~
        """
        pipeline_repr = yaml.safe_load(pipeline_str)
        with self.assertRaises(serializers.ValidationError):
            PipelineSourceFileSerializer.get_yaml_pipeline_canonical_representation(pipeline_repr)

    def test__parse_plugin_name_and_version(self):
        """
        Test that _parse_plugin_name_and_version returns the (name, version)
        tuple for the YAML 'plugin' string '<name> v<version>'.
        """
        name, version = PipelineSourceFileSerializer._parse_plugin_name_and_version(
            'simpledsapp v0.1')
        self.assertEqual(name, 'simpledsapp')
        self.assertEqual(version, '0.1')

    def test__parse_plugin_name_and_version_missing_version_raises(self):
        """
        Test that _parse_plugin_name_and_version raises ValidationError when
        the plugin string has no version (only one whitespace-separated token).
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSourceFileSerializer._parse_plugin_name_and_version(
                'simpledsapp')

    def test__convert_plugin_parameter_defaults(self):
        """
        Test that _convert_plugin_parameter_defaults converts a {name: default}
        mapping to the canonical list of {'name', 'default'} entries.
        """
        result = PipelineSourceFileSerializer._convert_plugin_parameter_defaults(
            {'a': 1, 'b': 'two'})
        self.assertIn({'name': 'a', 'default': 1}, result)
        self.assertIn({'name': 'b', 'default': 'two'}, result)
        self.assertEqual(len(result), 2)

    def test__convert_plugin_parameter_defaults_empty(self):
        """
        Test that _convert_plugin_parameter_defaults returns an empty list for
        an empty defaults dict.
        """
        self.assertEqual(
            PipelineSourceFileSerializer._convert_plugin_parameter_defaults({}),
            [])

    def test__build_canonical_yaml_node_full(self):
        """
        Test that _build_canonical_yaml_node produces the expected canonical
        node dict, including resource overrides and plugin_parameter_defaults.
        """
        node = {'title': 'simpledsapp1', 'plugin': 'simpledsapp v0.1',
                'previous': None, 'cpu_limit': '2500m',
                'memory_limit': '512Mi', 'number_of_workers': 2,
                'gpu_limit': 1,
                'plugin_parameter_defaults': {'dummyInt': 7}}
        canonical = PipelineSourceFileSerializer._build_canonical_yaml_node(node)
        self.assertEqual(canonical['title'], 'simpledsapp1')
        self.assertEqual(canonical['plugin_name'], 'simpledsapp')
        self.assertEqual(canonical['plugin_version'], '0.1')
        self.assertIsNone(canonical['previous'])
        self.assertEqual(canonical['cpu_limit'], '2500m')
        self.assertEqual(canonical['memory_limit'], '512Mi')
        self.assertEqual(canonical['number_of_workers'], 2)
        self.assertEqual(canonical['gpu_limit'], 1)
        self.assertEqual(canonical['plugin_parameter_defaults'],
                         [{'name': 'dummyInt', 'default': 7}])

    def test__build_canonical_yaml_node_omits_absent_resource_fields(self):
        """
        Test that _build_canonical_yaml_node omits resource keys that are not
        present on the source node, and omits plugin_parameter_defaults when
        empty.
        """
        node = {'title': 'simpledsapp1', 'plugin': 'simpledsapp v0.1',
                'previous': None}
        canonical = PipelineSourceFileSerializer._build_canonical_yaml_node(node)
        for f in ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit',
                  'plugin_parameter_defaults'):
            self.assertNotIn(f, canonical)

    def test__build_canonical_yaml_node_missing_plugin_raises(self):
        """
        Test that _build_canonical_yaml_node raises ValidationError when 'plugin'
        is missing.
        """
        with self.assertRaises(serializers.ValidationError):
            PipelineSourceFileSerializer._build_canonical_yaml_node(
                {'title': 'simpledsapp1', 'previous': None})

    def test__get_json_pipeline_canonical_representation(self):
        """
        Test whether custom get_json_pipeline_canonical_representation method returns an
        appropriate canonical JSON pipeline representation from the json representation.
        """
        pipeline_repr = json.loads(self.json_pipeline_str)
        canonical_repr = {'name': 'TestPipeline',
                          'locked': False,
                          'plugin_tree': '[{"title": "simpledsapp1", "plugin_name": "simpledsapp", "plugin_version": "0.1", "previous": null}, '
                                         '{"title": "simpledsapp2", "plugin_name": "simpledsapp", "plugin_version": "0.1", "previous": "simpledsapp1"}, '
                                         '{"title": "join", "plugin_name": "ts_copy", "plugin_version": "0.1", "previous": "simpledsapp1", '
                                         '"plugin_parameter_defaults": [{"name": "plugininstances", "default": "simpledsapp1,simpledsapp2"}]}]'}
        self.assertEqual(PipelineSourceFileSerializer.get_json_pipeline_canonical_representation(pipeline_repr),
                         canonical_repr)


class PluginPipingSerializerTests(SerializerTests):

    def setUp(self):
        super(PluginPipingSerializerTests, self).setUp()
        self.plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)

    def _make_create_serializer(self):
        """
        Build a PluginPipingSerializer that mimics how PipelineSerializer.validate_plugin_tree
        invokes it: no instance, plugin supplied via context.
        """
        return PluginPipingSerializer(data={}, context={'plugin': self.plugin})

    def _make_update_serializer(self):
        """
        Build a PluginPipingSerializer that mimics a PUT to PluginPipingDetail: bound to
        an existing PluginPiping whose plugin attribute is the test plugin.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        piping, _ = PluginPiping.objects.get_or_create(
            title='existing-piping', pipeline=pipeline, plugin=self.plugin)
        return PluginPipingSerializer(instance=piping, data={}, partial=True)

    def test_validate_gpu_limit_out_of_range_on_create(self):
        """
        Test whether overriden validate_gpu_limit method raises a serializers.ValidationError
        when the gpu_limit is not within the limits provided by the corresponding plugin
        (create context: plugin supplied via serializer context).
        """
        s = self._make_create_serializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_gpu_limit(self.plugin.min_gpu_limit - 1)
        with self.assertRaises(serializers.ValidationError):
            s.validate_gpu_limit(self.plugin.max_gpu_limit + 1)

    def test_validate_gpu_limit_out_of_range_on_update(self):
        """
        Test whether overriden validate_gpu_limit method raises a serializers.ValidationError
        when the gpu_limit is not within the limits provided by the corresponding plugin
        (update context: plugin taken from the bound instance).
        """
        s = self._make_update_serializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_gpu_limit(self.plugin.min_gpu_limit - 1)
        with self.assertRaises(serializers.ValidationError):
            s.validate_gpu_limit(self.plugin.max_gpu_limit + 1)

    def test_validate_gpu_limit_none_does_not_raise_on_create(self):
        """
        Test whether overriden validate_gpu_limit method does not raise when gpu_limit
        is None in the create context.
        """
        self.assertIsNone(self._make_create_serializer().validate_gpu_limit(None))

    def test_validate_gpu_limit_none_does_not_raise_on_update(self):
        """
        Test whether overriden validate_gpu_limit method does not raise when gpu_limit
        is None in the update context.
        """
        self.assertIsNone(self._make_update_serializer().validate_gpu_limit(None))

    def test_validate_number_of_workers_out_of_range_on_create(self):
        """
        Test whether overriden validate_number_of_workers method raises a
        serializers.ValidationError when the number_of_workers is not within the limits
        provided by the corresponding plugin (create context).
        """
        s = self._make_create_serializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_number_of_workers(self.plugin.min_number_of_workers - 1)
        with self.assertRaises(serializers.ValidationError):
            s.validate_number_of_workers(self.plugin.max_number_of_workers + 1)

    def test_validate_number_of_workers_out_of_range_on_update(self):
        """
        Test whether overriden validate_number_of_workers method raises a
        serializers.ValidationError when the number_of_workers is not within the limits
        provided by the corresponding plugin (update context).
        """
        s = self._make_update_serializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_number_of_workers(self.plugin.min_number_of_workers - 1)
        with self.assertRaises(serializers.ValidationError):
            s.validate_number_of_workers(self.plugin.max_number_of_workers + 1)

    def test_validate_number_of_workers_none_does_not_raise_on_create(self):
        """
        Test whether overriden validate_number_of_workers method does not raise when
        number_of_workers is None in the create context.
        """
        self.assertIsNone(
            self._make_create_serializer().validate_number_of_workers(None))

    def test_validate_number_of_workers_none_does_not_raise_on_update(self):
        """
        Test whether overriden validate_number_of_workers method does not raise when
        number_of_workers is None in the update context.
        """
        self.assertIsNone(
            self._make_update_serializer().validate_number_of_workers(None))

    def test_validate_cpu_limit_out_of_range_on_create(self):
        """
        Test whether overriden validate_cpu_limit method raises a serializers.ValidationError
        when the cpu_limit is not within the limits provided by the corresponding plugin
        (create context).
        """
        s = self._make_create_serializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_cpu_limit(self.plugin.min_cpu_limit - 1)
        with self.assertRaises(serializers.ValidationError):
            s.validate_cpu_limit(self.plugin.max_cpu_limit + 1)

    def test_validate_cpu_limit_out_of_range_on_update(self):
        """
        Test whether overriden validate_cpu_limit method raises a serializers.ValidationError
        when the cpu_limit is not within the limits provided by the corresponding plugin
        (update context).
        """
        s = self._make_update_serializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_cpu_limit(self.plugin.min_cpu_limit - 1)
        with self.assertRaises(serializers.ValidationError):
            s.validate_cpu_limit(self.plugin.max_cpu_limit + 1)

    def test_validate_cpu_limit_none_does_not_raise_on_create(self):
        """
        Test whether overriden validate_cpu_limit method does not raise when cpu_limit
        is None in the create context.
        """
        self.assertIsNone(self._make_create_serializer().validate_cpu_limit(None))

    def test_validate_cpu_limit_none_does_not_raise_on_update(self):
        """
        Test whether overriden validate_cpu_limit method does not raise when cpu_limit
        is None in the update context.
        """
        self.assertIsNone(self._make_update_serializer().validate_cpu_limit(None))

    def test_validate_memory_limit_out_of_range_on_create(self):
        """
        Test whether overriden validate_memory_limit method raises a
        serializers.ValidationError when the memory_limit is not within the limits
        provided by the corresponding plugin (create context).
        """
        s = self._make_create_serializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_memory_limit(self.plugin.min_memory_limit - 1)
        with self.assertRaises(serializers.ValidationError):
            s.validate_memory_limit(self.plugin.max_memory_limit + 1)

    def test_validate_memory_limit_out_of_range_on_update(self):
        """
        Test whether overriden validate_memory_limit method raises a
        serializers.ValidationError when the memory_limit is not within the limits
        provided by the corresponding plugin (update context).
        """
        s = self._make_update_serializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_memory_limit(self.plugin.min_memory_limit - 1)
        with self.assertRaises(serializers.ValidationError):
            s.validate_memory_limit(self.plugin.max_memory_limit + 1)

    def test_validate_memory_limit_none_does_not_raise_on_create(self):
        """
        Test whether overriden validate_memory_limit method does not raise when
        memory_limit is None in the create context.
        """
        self.assertIsNone(self._make_create_serializer().validate_memory_limit(None))

    def test_validate_memory_limit_none_does_not_raise_on_update(self):
        """
        Test whether overriden validate_memory_limit method does not raise when
        memory_limit is None in the update context.
        """
        self.assertIsNone(self._make_update_serializer().validate_memory_limit(None))

    def test_title_is_writable_on_create(self):
        """
        Test that the title field is writable when no instance is bound (create
        context), so PipelineSerializer.validate_plugin_tree can validate it.
        """
        s = PluginPipingSerializer(data={'title': 'a-title'},
                                   context={'plugin': self.plugin})
        self.assertFalse(s.fields['title'].read_only)

    def test_title_is_read_only_on_update(self):
        """
        Test that the title field is forced to read-only when an instance is bound
        (update context), so a PUT to PluginPipingDetail can never rename the piping.
        """
        s = self._make_update_serializer()
        self.assertTrue(s.fields['title'].read_only)
