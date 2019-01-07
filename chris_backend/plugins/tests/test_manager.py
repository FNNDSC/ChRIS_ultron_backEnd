
import logging
import os
import time
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User

from plugins.models import Plugin, PluginParameter, PluginInstance, ComputeResource
from plugins.services import manager


class PluginManagerTests(TestCase):
    
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
        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_dock_image = "fnndsc/pl-simpledsapp"
        self.username = 'data/foo'
        self.password = 'foo-pass'
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

    def test_mananger_can_get_plugin(self):
        """
        Test whether the manager can return a plugin object.
        """
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        self.assertEqual(plugin, self.pl_manager.get_plugin(self.plugin_fs_name))

    def test_mananger_can_add_plugin(self):
        """
        Test whether the manager can add a new plugin to the system.
        """
        self.plugin_repr['name'] = 'testapp'
        # mock manager's get_plugin_representation_from_store static method
        self.pl_manager.get_plugin_representation_from_store = mock.Mock(
            return_value=self.plugin_repr)
        self.pl_manager.run(['add', 'testapp', 'host', 'http://localhost:8010/api/v1/'])
        self.assertEqual(Plugin.objects.count(), 2)
        self.assertTrue(PluginParameter.objects.count() > 1)
        self.pl_manager.get_plugin_representation_from_store.assert_called_with(
            'testapp', 'http://localhost:8010/api/v1/', None, None, 30)

    def test_mananger_can_modify_plugin(self):
        """
        Test whether the manager can modify an existing plugin.
        """
        self.plugin_repr['selfexec'] = 'testapp.py'
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        initial_modification_date = plugin.modification_date
        time.sleep(1)
        # mock manager's get_plugin_representation_from_store static method
        self.pl_manager.get_plugin_representation_from_store = mock.Mock(
            return_value=self.plugin_repr)
        self.pl_manager.run(['modify', self.plugin_fs_name, '--computeresource', 'host1',
                             '--storeurl', 'http://localhost:8010/api/v1/'])
        self.pl_manager.get_plugin_representation_from_store.assert_called_with(
            'simplefsapp', 'http://localhost:8010/api/v1/', None, None, 30)

        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        self.assertTrue(plugin.modification_date > initial_modification_date)
        self.assertEqual(plugin.selfexec,'testapp.py')
        self.assertEqual(plugin.compute_resource.compute_resource_identifier, 'host1')

    def test_mananger_can_remove_plugin(self):
        """
        Test whether the manager can remove an existing plugin from the system.
        """
        self.pl_manager.run(['remove', self.plugin_fs_name])
        self.assertEqual(Plugin.objects.count(), 0)
        self.assertEqual(PluginParameter.objects.count(), 0)

    def test_mananger_can_run_registered_plugin_app(self):
        """
        Test whether the manager can run an already registered plugin app.
        """
        with mock.patch.object(manager.charm.Charm, '__init__',
                               return_value=None) as charm_init_mock:
            with mock.patch.object(manager.charm.Charm, 'app_manage',
                                   return_value=None) as charm_app_manage_mock:
                user = User.objects.get(username=self.username)
                plugin = Plugin.objects.get(name=self.plugin_fs_name)
                pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                            compute_resource=plugin.compute_resource)
                parameter_dict = {'dir': './'}

                self.pl_manager.run_plugin_app(pl_inst,
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
        self.pl_manager.run_plugin_app(pl_inst,
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
        with mock.patch.object(manager.charm.Charm, '__init__',
                               return_value=None) as charm_init_mock:
            with mock.patch.object(manager.charm.Charm, 'app_statusCheckAndRegister',
                                   return_value=None) as app_statusCheckAndRegister_mock:

                user = User.objects.get(username=self.username)
                plugin = Plugin.objects.get(name=self.plugin_fs_name)
                pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                    compute_resource=plugin.compute_resource)

                self.pl_manager.check_plugin_app_exec_status(pl_inst)
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

        self.pl_manager.run_plugin_app(pl_inst,
                                       parameter_dict,
                                       service             = 'pfcon',
                                       inputDirOverride    = '/share/incoming',
                                       outputDirOverride   = '/share/outgoing')

        self.pl_manager.check_plugin_app_exec_status(pl_inst)
        self.assertEqual(pl_inst.status, 'started')

        # In the following we keep checking the status until the job ends with
        # 'finishedSuccessfully'. The code runs in a lazy loop poll with a
        # max number of attempts at 2 second intervals.
        maxLoopTries    = 20
        currentLoop     = 1
        b_checkAgain    = True
        while b_checkAgain:
            str_responseStatus = self.pl_manager.check_plugin_app_exec_status(pl_inst)
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
