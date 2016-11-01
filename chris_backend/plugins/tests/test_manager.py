
import os, shutil

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings

from plugins.models import Plugin, PluginParameter, PluginInstance
from plugins.services.manager import PluginManager

import time

import pudb

class PluginManagerTests(TestCase):
    
    def setUp(self):
        self.plugin_fs_name = "simplefsapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': False}}
        self.plugin_ds_name = "simpledsapp"
        self.username = 'foo'
        self.password = 'foo-pass'

        # create a plugin
        (plugin_fs, tf) = Plugin.objects.get_or_create(name=self.plugin_fs_name,
                                                    type='fs')
        # add plugin's parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])

        # create user
        user = User.objects.create_user(username=self.username,
                                        password=self.password)

    def test_mananger_can_add_plugin(self):
        """
        Test whether the manager can add a new plugin app to the system.
        """
        pl_manager = PluginManager()
        pl_manager.run(['--add', self.plugin_ds_name])
        self.assertEquals(Plugin.objects.count(), 2)
        self.assertTrue(PluginParameter.objects.count() > 1)

    def test_mananger_can_remove_plugin(self):
        """
        Test whether the manager can remove an existing plugin app from the system.
        """
        pl_manager = PluginManager()
        pl_manager.run(['--remove', self.plugin_fs_name])
        self.assertEquals(Plugin.objects.count(), 0)
        self.assertEquals(PluginParameter.objects.count(), 0)

    def test_mananger_can_register_plugin_modification_date(self):
        """
        Test whether the manager can register a new modification date for an
        existing plugin.
        """
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        initial_modification_date = plugin.modification_date
        pl_manager = PluginManager()
        pl_manager.run(['--modify', self.plugin_fs_name])
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        self.assertTrue(plugin.modification_date > initial_modification_date)

    def test_mananger_can_run_registered_plugin_app(self):
        """
        Test whether the manager can run an already registered plugin app.
        """
         # create test directory where files are created
        test_dir = settings.MEDIA_ROOT + '/test'
        settings.MEDIA_ROOT = test_dir
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)

        # pudb.set_trace()

        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user)
        parameter_dict = {'dir': './'}
        pl_manager = PluginManager()
        pl_manager.run_plugin_app(pl_inst, parameter_dict)
        time.sleep(5)
        self.assertTrue(os.path.isfile(os.path.join(pl_inst.get_output_path(), 'out.txt')))

        #remove test directory
        shutil.rmtree(test_dir)
        settings.MEDIA_ROOT = os.path.dirname(test_dir)


