
import logging

from django.test import TestCase

from plugins.models import Plugin, PluginParameter
from plugins.models import ComputeResource


class PluginModelTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.plugin_fs_name = "simplefsapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': False}}
        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
                                                        compute_resource_identifier="host")
        # create a plugin
        (plugin_fs, tf) = Plugin.objects.get_or_create(name=self.plugin_fs_name,
                                                    type='fs',
                                                    compute_resource=self.compute_resource)
        # add plugins' parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])

    def test_get_plugin_parameter_names(self):
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        param_names = plugin.get_plugin_parameter_names()
        self.assertEqual(param_names, ['dir'])

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)
