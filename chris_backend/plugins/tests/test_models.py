
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
            name="host", description="host description")

        # create a plugin
        (plugin_fs, tf) = Plugin.objects.get_or_create(name=self.plugin_fs_name, type='fs')
        plugin_fs.compute_resources.set([self.compute_resource])
        plugin_fs.save()

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


class ComputeResourceModelTests(ModelTests):
    """
    Test the ComputeResource model.
    """

    def test_delete(self):
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        # test the failure case bc plugin would be left without a compute resource
        with self.assertRaises(Exception):
            self.compute_resource.delete()
        # test the success case
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="test", description="test description")
        plugin_compute_resources = list(plugin.compute_resources.all())
        plugin_compute_resources.append(compute_resource)
        plugin.compute_resources.set(plugin_compute_resources)
        plugin.save()
        n_cr = len(plugin_compute_resources)
        compute_resource.delete()
        self.assertEqual(plugin.compute_resources.all().count(), n_cr - 1)


class PluginModelTests(ModelTests):
    """
    Test the Plugin model.
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
