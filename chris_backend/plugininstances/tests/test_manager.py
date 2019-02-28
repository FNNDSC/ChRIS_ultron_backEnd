
import logging
import os
import time
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User

from plugins.models import Plugin, PluginParameter
from plugininstances.models import PluginInstance, ComputeResource
from plugininstances.services import manager


class PluginAppManagerTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.plugin_repr = {"name": "simplefsapp", "dock_image": "fnndsc/pl-simplefsapp",
                            "authors": "FNNDSC (dev@babyMRI.org)", "type": "fs",
                            "description": "A simple chris fs app demo", "version": "0.1",
                            "title": "Simple chris fs app", "license": "Opensource (MIT)",

                            "parameters": [{"optional": True, "action": "store",
                                            "help": "look up directory", "type": "path",
                                            "name": "dir", "flag": "--dir",
                                            "default": "./"}],

                            "selfpath": "/usr/src/simplefsapp",
                            "selfexec": "simplefsapp.py", "execshell": "python3"}

        self.plugin_fs_name = "simplefsapp"
        self.username = 'data/foo'
        self.password = 'foo-pass'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create a plugin
        data = self.plugin_repr.copy()
        parameters = self.plugin_repr['parameters']
        del data['parameters']
        data['compute_resource'] = self.compute_resource
        (plugin_fs, tf) = Plugin.objects.get_or_create(**data)

        # add plugin's parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'])

        # create user
        User.objects.create_user(username=self.username, password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)

    def test_mananger_can_run_registered_plugin_app(self):
        """
        Test whether the manager can run an already registered plugin app.
        """
        with mock.patch.object(manager.Charm, '__init__',
                               return_value=None) as charm_init_mock:
            with mock.patch.object(manager.Charm, 'app_manage',
                                   return_value=None) as charm_app_manage_mock:
                user = User.objects.get(username=self.username)
                plugin = Plugin.objects.get(name=self.plugin_fs_name)
                pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                            compute_resource=plugin.compute_resource)
                parameter_dict = {'dir': './'}

                manager.PluginAppManager.run_plugin_app(pl_inst,
                                               parameter_dict,
                                               service='pfcon',
                                               inputDirOverride='/share/incoming',
                                               outputDirOverride='/share/outgoing',
                                               )
                self.assertEqual(pl_inst.status, 'started')
                assert charm_init_mock.called
                charm_app_manage_mock.assert_called_with(method='pfcon', IOPhost='host')

    @tag('integration')
    def test_integration_mananger_can_run_registered_plugin_app(self):
        """
        Test whether the manager can run an already registered plugin app.

        NB: Note the directory overrides on input and output dirs! This
            is file system space in the plugin container, and thus by hardcoding
            this here we are relying on totally out-of-band knowledge! 

            This must be fixed in later versions!
        """
        # try:
        #     # create test directory where files are created
        #     test_dir = settings.MEDIA_ROOT + '/test'
        #     settings.MEDIA_ROOT = test_dir
        #     if not os.path.exists(test_dir):
        #         os.makedirs(test_dir)

        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                            compute_resource=plugin.compute_resource)
        parameter_dict = {'dir': './'}
        manager.PluginAppManager.run_plugin_app(pl_inst,
                                       parameter_dict,
                                       service             = 'pfcon',
                                       inputDirOverride    = '/share/incoming',
                                       outputDirOverride   = '/share/outgoing')
        self.assertEqual(pl_inst.status, 'started')

        # finally:
        #     # remove test directory
        #     shutil.rmtree(test_dir, ignore_errors=True)
        #     settings.MEDIA_ROOT = os.path.dirname(test_dir)

    def test_mananger_can_check_plugin_app_exec_status(self):
        """
        Test whether the manager can check a plugin's app execution status
        """
        with mock.patch.object(manager.Charm, '__init__',
                               return_value=None) as charm_init_mock:
            with mock.patch.object(manager.Charm, 'app_statusCheckAndRegister',
                                   return_value=None) as app_statusCheckAndRegister_mock:

                user = User.objects.get(username=self.username)
                plugin = Plugin.objects.get(name=self.plugin_fs_name)
                pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                    compute_resource=plugin.compute_resource)

                manager.PluginAppManager.check_plugin_app_exec_status(pl_inst)
                self.assertEqual(pl_inst.status, 'started')
                charm_init_mock.assert_called_with(plugin_inst=pl_inst)
                app_statusCheckAndRegister_mock.assert_called_with()

    @tag('integration', 'error-pman')
    def test_integration_mananger_can_check_plugin_app_exec_status(self):
        """
        Test whether the manager can check a plugin's app execution status.

        NB: Note the directory overrides on input and output dirs! This
            is file system space in the plugin container, and thus by hardcoding
            this here we are relying on totally out-of-band knowledge! 

            This must be fixed in later versions!
        """
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                compute_resource=plugin.compute_resource)
        parameter_dict = {'dir': './'}

        manager.PluginAppManager.run_plugin_app(pl_inst,
                                       parameter_dict,
                                       service             = 'pfcon',
                                       inputDirOverride    = '/share/incoming',
                                       outputDirOverride   = '/share/outgoing')

        manager.PluginAppManager.check_plugin_app_exec_status(pl_inst)
        self.assertEqual(pl_inst.status, 'started')

        # In the following we keep checking the status until the job ends with
        # 'finishedSuccessfully'. The code runs in a lazy loop poll with a
        # max number of attempts at 2 second intervals.
        maxLoopTries    = 20
        currentLoop     = 1
        b_checkAgain    = True
        while b_checkAgain:
            str_responseStatus = manager.PluginAppManager.check_plugin_app_exec_status(pl_inst)
            if str_responseStatus == 'finishedSuccessfully':
                b_checkAgain = False
            else:
                time.sleep(2)
            currentLoop += 1
            if currentLoop == maxLoopTries:
                b_checkAgain = False

        # if pl_inst.status != 'finishedSuccessfully':
        #     pudb.set_trace()
        self.assertEqual(pl_inst.status, 'finishedSuccessfully')

        str_fileCreatedByPlugin     = os.path.join(pl_inst.get_output_path(), 'out.txt')
        str_ABSfileCreatedByPlugin  = '/' + str_fileCreatedByPlugin
        self.assertTrue(os.path.isfile(str_ABSfileCreatedByPlugin))
