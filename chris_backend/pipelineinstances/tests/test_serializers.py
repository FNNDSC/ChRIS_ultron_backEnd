
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
from pipelines.models import Pipeline, PluginPiping
from pipelineinstances.models import PipelineInstance
from pipelineinstances.serializers import PipelineInstanceSerializer


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
        (plg_param_ds, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyInt',
            type=self.plugin_ds_parameters['dummyInt']['type'],
            optional=self.plugin_ds_parameters['dummyInt']['optional']
        )
        default = self.plugin_ds_parameters['dummyInt']['default']
        DefaultIntParameter.objects.get_or_create(plugin_param=plg_param_ds,
                                                  value=default)  # set plugin parameter default

        # create user
        user = User.objects.create_user(username=self.username, password=self.password)

        # create a pipeline
        self.pipeline_name = 'Pipeline1'
        (pipeline, tf) = Pipeline.objects.get_or_create(name=self.pipeline_name,
                                                        owner=user, category='test')

        # create two plugin pipings
        self.pips = []
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds,
                                                       pipeline=pipeline)
        self.pips.append(pip)
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds, previous=pip,
                                                       pipeline=pipeline)
        self.pips.append(pip)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class PipelineInstanceSerializerTests(SerializerTests):

    def setUp(self):
        super(PipelineInstanceSerializerTests, self).setUp()

    def test_create(self):
        """
        Test whether overriden 'create' method successfully creates a new pipeline
        instance after deleting 'previous_plugin_inst_id' from serializer data as it's
        not a model field.
        """
        owner = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=owner, compute_resource=plugin.compute_resources.all()[0])
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        data = {'title': 'PipelineInst1', 'previous_plugin_inst_id': pl_inst.id}
        pipeline_inst_serializer = PipelineInstanceSerializer(data=data)
        pipeline_inst_serializer.is_valid(raise_exception=True)
        pipeline_inst_serializer.validated_data['pipeline'] = pipeline
        pipeline_inst_serializer.validated_data['owner'] = owner
        pipeline_inst = pipeline_inst_serializer.create(pipeline_inst_serializer.validated_data)
        self.assertNotIn('previous_plugin_inst_id', pipeline_inst_serializer.validated_data)
        self.assertIsInstance(pipeline_inst, PipelineInstance)

    def test_validate_previous_plugin_inst(self):
        """
        Test whether custom validate_previous_plugin_inst method validates that an integer
        id is provided for previous instance. Then checks that the id exists in the DB and
        that the user can run plugins within the corresponding feed.
        """
        owner = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=owner, compute_resource=plugin.compute_resources.all()[0])
        data = {'title': 'PipelineInst1', 'previous_plugin_inst_id': pl_inst.id}
        pipeline_inst_serializer = PipelineInstanceSerializer(data=data)
        pipeline_inst_serializer.context['request'] = mock.Mock()
        pipeline_inst_serializer.context['request'].user = owner
        with self.assertRaises(serializers.ValidationError):
            pipeline_inst_serializer.validate_previous_plugin_inst(None)
        with self.assertRaises(serializers.ValidationError):
            pipeline_inst_serializer.validate_previous_plugin_inst(pl_inst.id+1)
        # create another user
        another_user = User.objects.create_user(username='boo', password='far')
        with self.assertRaises(serializers.ValidationError):
            pipeline_inst_serializer.context['request'].user = another_user
            pipeline_inst_serializer.validate_previous_plugin_inst(pl_inst.id)

    def test_parse_parameters(self):
        """
        Test whether custom parse_parameters method properly parses the pipeline instance
        parameters in the request data dictionary.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)
        pipeline_inst_serializer = PipelineInstanceSerializer()
        pipeline_inst_serializer.context['request'] = mock.Mock()
        # parameters name in the request have the form
        # < plugin.id > _ < piping.id > _ < previous_piping.id > _ < param.name >
        param_name = "%s_%s_%s_%s" % (plugin.id, self.pips[1].id, self.pips[0].id, 'dummy_Int')
        pipeline_inst_serializer.context['request'].data = {param_name: 1122}
        parsed_params_dict = pipeline_inst_serializer.parse_parameters()
        self.assertEqual(parsed_params_dict, {self.pips[1].id: {'dummy_Int': 1122}})
