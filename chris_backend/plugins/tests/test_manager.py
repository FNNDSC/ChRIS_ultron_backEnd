
import logging
import time
from unittest import mock

from django.test import TestCase

from plugins.models import Plugin
from plugins.models import PluginParameter, DefaultStrParameter
from plugins.models import ComputeResource
from plugins.services import manager


class PluginManagerTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.plugin_repr = {"name": "simplecopyapp", "dock_image": "fnndsc/pl-simplecopyapp",
                            "authors": "FNNDSC (dev@babyMRI.org)", "type": "fs",
                            "description": "A simple chris fs app demo", "version": "0.1",
                            "title": "Simple chris fs app", "license": "Opensource (MIT)",

                            "parameters": [{"optional": True, "action": "store",
                                            "help": "look up directory", "type": "string",
                                            "name": "dir", "flag": "--dir",
                                            "default": "./"}],

                            "selfpath": "/usr/src/simplecopyapp",
                            "selfexec": "simplecopyapp.py", "execshell": "python3"}

        self.plugin_fs_name = "simplecopyapp"
        self.pl_manager = manager.PluginManager()

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create a plugin
        data = self.plugin_repr.copy()
        parameters = self.plugin_repr['parameters']
        del data['parameters']
        data['compute_resource'] = self.compute_resource
        (plugin_fs, tf) = Plugin.objects.get_or_create(**data)

        # add plugin's parameters
        (plg_param, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'],
            optional=parameters[0]['optional']
        )
        default = parameters[0]['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param, value=default)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)

    def test_mananger_can_get_plugin(self):
        """
        Test whether the manager can return a plugin object.
        """
        plugin = Plugin.objects.get(name=self.plugin_fs_name, version="0.1")
        self.assertEqual(plugin, self.pl_manager.get_plugin(self.plugin_fs_name, "0.1"))

    def test_mananger_can_add_plugin(self):
        """
        Test whether the manager can add a new plugin to the system.
        """
        self.plugin_repr['name'] = 'testapp'
        # mock manager's get_plugin_representation_from_store static method
        self.pl_manager.get_plugin_representation_from_store = mock.Mock(
            return_value=self.plugin_repr)
        self.pl_manager.run(['add', 'testapp', 'host', 'http://localhost:8010/api/v1/',
                             '--version', '0.1'])
        self.assertEqual(Plugin.objects.count(), 2)
        self.assertTrue(PluginParameter.objects.count() > 1)
        self.pl_manager.get_plugin_representation_from_store.assert_called_with(
            'testapp', 'http://localhost:8010/api/v1/', '0.1', None, None, None)

    def test_mananger_can_modify_plugin(self):
        """
        Test whether the manager can modify an existing plugin.
        """
        self.plugin_repr['dock_image'] = 'fnndsc/pl-simplecopyapp1111'
        plugin = Plugin.objects.get(name=self.plugin_fs_name, version='0.1')
        initial_modification_date = plugin.modification_date
        time.sleep(1)
        # mock manager's get_plugin_representation_from_store static method
        self.pl_manager.get_plugin_representation_from_store = mock.Mock(
            return_value=self.plugin_repr)
        self.pl_manager.run(['modify', self.plugin_fs_name, '0.1', '--computeresource',
                             'host1', '--storeurl', 'http://localhost:8010/api/v1/'])
        self.pl_manager.get_plugin_representation_from_store.assert_called_with(
            'simplecopyapp', 'http://localhost:8010/api/v1/', '0.1', None, None, None)

        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        self.assertTrue(plugin.modification_date > initial_modification_date)
        self.assertEqual(plugin.dock_image,'fnndsc/pl-simplecopyapp1111')
        self.assertEqual(plugin.compute_resource.compute_resource_identifier, 'host1')

    def test_mananger_can_remove_plugin(self):
        """
        Test whether the manager can remove an existing plugin from the system.
        """
        self.pl_manager.run(['remove', self.plugin_fs_name, "0.1"])
        self.assertEqual(Plugin.objects.count(), 0)
        self.assertEqual(PluginParameter.objects.count(), 0)
