
import logging

from django.test import TestCase

from plugins.models import Plugin
from plugins.models import PluginParameter, DefaultStrParameter
from plugins.models import ComputeResource


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.plugin_fs_name = "simplecopyapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': True,
                                             'default': "./"}}
        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
                                                        compute_resource_identifier="host")
        # create a plugin
        (plugin_fs, tf) = Plugin.objects.get_or_create(name=self.plugin_fs_name,
                                                    type='fs',
                                                    compute_resource=self.compute_resource)
        # add plugins' parameters
        (plg_param, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional']
        )
        default = self.plugin_fs_parameters['dir']['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param, value=default)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PluginModelTests(ModelTests):
    """
    Test the PluginModel model.
    """

    def test_get_plugin_parameter_names(self):
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        param_names = plugin.get_plugin_parameter_names()
        self.assertEqual(param_names, ['dir'])


class PluginParameterModelTests(ModelTests):
    """
    Test the PluginParameter model.
    """

    def test_get_default(self):
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        parameter = plugin.parameters.get(name='dir')
        default = parameter.get_default()
        self.assertEqual(default.value, "./")
