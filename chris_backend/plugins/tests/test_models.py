
import logging

from django.test import TestCase

from plugins.models import PluginMeta, PluginMetaFilter, Plugin
from plugins.models import PluginParameter, DefaultStrParameter
from plugins.models import ComputeResource


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.plugin_fs_name = "simplecopyapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': True,
                                             'default': "./"}}

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", description="host description")

        # create a plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_fs_name, type='fs')
        (plugin_fs, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
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
        logging.disable(logging.NOTSET)


class ComputeResourceModelTests(ModelTests):
    """
    Test the ComputeResource model.
    """

    def test_delete(self):
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
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


class PluginMetaFilterTests(ModelTests):

    def setUp(self):
        super(PluginMetaFilterTests, self).setUp()
        self.other_plugin_name = "simplefsapp1"

        # create other plugin
        (meta, tf) = PluginMeta.objects.get_or_create(name=self.other_plugin_name)
        Plugin.objects.get_or_create(meta=meta)

    def test_search_name_authors_category(self):
        """
        Test whether custom method search_name_authors_category returns a filtered
        queryset with all plugins for which name or title or category matches the
        search value.
        """
        meta1 = PluginMeta.objects.get(name=self.plugin_fs_name)
        meta1.category = 'dir'
        meta1.authors = 'author1'
        meta1.save()
        meta2 = PluginMeta.objects.get(name=self.other_plugin_name)
        meta2.category = 'dir'
        meta2.authors = 'author2'
        meta2.save()
        meta_filter = PluginMetaFilter()
        queryset = PluginMeta.objects.all()
        qs = meta_filter.search_name_authors_category(queryset, 'name_authors_category', 'Dir')
        self.assertCountEqual(qs, queryset)


class PluginModelTests(ModelTests):
    """
    Test the Plugin model.
    """

    def test_get_plugin_parameter_names(self):
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        param_names = plugin.get_plugin_parameter_names()
        self.assertEqual(param_names, ['dir'])


class PluginParameterModelTests(ModelTests):
    """
    Test the PluginParameter model.
    """

    def test_get_default(self):
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        parameter = plugin.parameters.get(name='dir')
        default = parameter.get_default()
        self.assertEqual(default.value, "./")
