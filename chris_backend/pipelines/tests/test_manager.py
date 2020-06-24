
import logging
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, tag

from plugins.models import PluginMeta, Plugin, PluginParameter, DefaultIntParameter
from plugins.models import ComputeResource
from pipelines.models import Pipeline, PluginPiping
from pipelines.services import manager


class PipelineManagerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_version = "0.1"
        self.plugin_ds_parameters = {'dummyInt': {'type': 'integer', 'optional': True,
                                                  'default': 111111}}
        self.username = 'foo'
        self.password = 'foo-pass'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", description="host description")

        # create plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ds_name, type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version=self.plugin_ds_version)
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

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

        # create user
        user = User.objects.create_user(username=self.username, password=self.password)

        # create a pipeline
        self.pipeline_name = 'Pipeline1'
        (pipeline, tf) = Pipeline.objects.get_or_create(name=self.pipeline_name, owner=user, category='test')

        # create two plugin pipings
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds, pipeline=pipeline)
        PluginPiping.objects.get_or_create(plugin=plugin_ds, previous=pip, pipeline=pipeline)

        self.pipeline_manager = manager.PipelineManager()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_mananger_can_add_pipeline(self):
        """
        Test whether the manager can add a new pipeline to the system.
        """
        plugin_tree = '[{"plugin_name": "simpledsapp", "plugin_version": "0.1", "previous_index": null}, ' \
                      '{"plugin_name": "simpledsapp", "plugin_version": "0.1", "previous_index": 0}]'
        self.pipeline_manager.run(['add', 'Pipeline2', self.username, plugin_tree, '--unlock'])
        self.assertEqual(Pipeline.objects.count(), 2)

    def test_mananger_can_modify_pipeline(self):
        """
        Test whether the manager can modify an existing pipeline.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        initial_modification_date = pipeline.modification_date
        self.pipeline_manager.run(['modify', str(pipeline.id), '--name', 'Pipeline2'])
        pipeline = Pipeline.objects.get(pk=pipeline.id)
        self.assertTrue(pipeline.modification_date > initial_modification_date)
        self.assertEqual(pipeline.name, 'Pipeline2')

    def test_mananger_can_remove_pipeline(self):
        """
        Test whether the manager can remove an existing pipeline from the system.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        self.pipeline_manager.run(['remove', str(pipeline.id)])
        self.assertEqual(Pipeline.objects.count(), 0)
        self.assertEqual(PluginPiping.objects.count(), 0)

    def test_mananger_can_get_pipeline(self):
        """
        Test whether the manager can return a pipeline object.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        self.assertEqual(pipeline, self.pipeline_manager.get_pipeline(pipeline.id))
