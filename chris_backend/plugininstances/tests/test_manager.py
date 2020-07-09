
import logging
import os
import time
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.conf import settings

import swiftclient

from plugins.models import PluginMeta, Plugin
from plugins.models import PluginParameter
from plugininstances.models import PluginInstance, PathParameter, ComputeResource
from plugininstances.services.manager import PluginInstanceManager


class PluginInstanceManagerTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.plugin_fs_name = "simplefsapp"
        self.username = 'foo'
        self.password = 'foo-pass'

        plugin_parameters = [{'name': 'dir', 'type': 'path', 'action': 'store',
                              'optional': False, 'flag': '--dir', 'short_flag': '-d',
                              'help': 'test plugin', 'ui_exposed': True}]

        self.plg_data = {'title': 'Dir plugin',
                         'description': 'A simple chris fs app demo',
                         'version': '0.1',
                         'dock_image': 'fnndsc/pl-simplefsapp',
                         'execshell': 'python3',
                         'selfpath': '/usr/src/simplefsapp',
                         'selfexec': 'simplefsapp.py'}

        self.plg_meta_data = {'name': self.plugin_fs_name,
                              'license': 'MIT',
                              'type': 'fs',
                              'icon': 'http://github.com/plugin',
                              'category': 'Dir',
                              'stars': 0,
                              'authors': 'FNNDSC (dev@babyMRI.org)'}

        self.plugin_repr = self.plg_data.copy()
        self.plugin_repr.update(self.plg_meta_data)
        self.plugin_repr['parameters'] = plugin_parameters

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", description="host description")

        # create a plugin
        data = self.plg_meta_data.copy()
        (pl_meta, tf) = PluginMeta.objects.get_or_create(**data)
        data = self.plg_data.copy()
        (plugin_fs, tf) = Plugin.objects.get_or_create(meta=pl_meta, **data)
        plugin_fs.compute_resources.set([self.compute_resource])
        plugin_fs.save()

        # add plugin's parameters
        parameters = plugin_parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'],
            optional=parameters[0]['optional'],
        )

        # create user
        User.objects.create_user(username=self.username, password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_mananger_can_run_registered_plugin_app(self):
        """
        Test whether the manager can run an already registered plugin app.
        """
        with mock.patch.object(PluginInstanceManager, 'app_service_call',
                               return_value='response') as app_service_call_mock:
            user = User.objects.get(username=self.username)
            plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
            (pl_inst, tf) = PluginInstance.objects.get_or_create(
                plugin=plugin, owner=user,
                compute_resource=plugin.compute_resources.all()[0])
            pl_param = plugin.parameters.all()[0]
            PathParameter.objects.get_or_create(plugin_inst=pl_inst,
                                                plugin_param=pl_param,
                                                value=self.username)
            parameter_dict = {'dir': self.username}
            plg_inst_manager = PluginInstanceManager(pl_inst)
            plg_inst_manager.run_plugin_instance_app(parameter_dict)
            self.assertEqual(pl_inst.status, 'started')
            app_service_call_mock.assert_called_once()

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
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        pl_param = plugin.parameters.all()[0]
        PathParameter.objects.get_or_create(plugin_inst=pl_inst, plugin_param=pl_param,
                                            value=self.username)
        parameter_dict = {'dir': self.username}
        plg_inst_manager = PluginInstanceManager(pl_inst)
        plg_inst_manager.run_plugin_instance_app(parameter_dict)
        self.assertEqual(pl_inst.status, 'started')

        # finally:
        #     # remove test directory
        #     shutil.rmtree(test_dir, ignore_errors=True)
        #     settings.MEDIA_ROOT = os.path.dirname(test_dir)

    def test_mananger_can_check_plugin_instance_app_exec_status(self):
        """
        Test whether the manager can check a plugin's app execution status
        """
        pass
        # with mock.patch.object(PluginInstanceManager, 'app_service_call',
        #                        return_value='response') as app_service_call_mock:
        #
        #     user = User.objects.get(username=self.username)
        #     plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        #     (pl_inst, tf) = PluginInstance.objects.get_or_create(
        #         plugin=plugin, owner=user,
        #         compute_resource=plugin.compute_resources.all()[0])
        #     pl_param = plugin.parameters.all()[0]
        #     PathParameter.objects.get_or_create(plugin_inst=pl_inst,
        #                                         plugin_param=pl_param,
        #                                         value=self.username)
        #     plg_inst_manager = PluginInstanceManager(pl_inst)
        #     plg_inst_manager.check_plugin_instance_app_exec_status()
        #     self.assertEqual(pl_inst.status, 'started')
        #     msg = {
        #         "action": "status",
        #         "meta": {
        #             "remote": {
        #                 "key": plg_inst_manager.str_jid_prefix + str(pl_inst.id)
        #             }
        #         }
        #     }
        #     app_service_call_mock.assert_called_with(msg)

    @tag('integration', 'error-pman')
    def test_integration_mananger_can_check_plugin_instance_app_exec_status(self):
        """
        Test whether the manager can check a plugin's app execution status.

        NB: Note the directory overrides on input and output dirs! This
            is file system space in the plugin container, and thus by hardcoding
            this here we are relying on totally out-of-band knowledge! 

            This must be fixed in later versions!
        """

        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        pl_param = plugin.parameters.all()[0]
        PathParameter.objects.get_or_create(plugin_inst=pl_inst, plugin_param=pl_param,
                                            value=self.username)
        parameter_dict = {'dir': self.username}

        plg_inst_manager = PluginInstanceManager(pl_inst)
        plg_inst_manager.run_plugin_instance_app(parameter_dict)

        plg_inst_manager.check_plugin_instance_app_exec_status()
        self.assertEqual(pl_inst.status, 'started')

        # In the following we keep checking the status until the job ends with
        # 'finishedSuccessfully'. The code runs in a lazy loop poll with a
        # max number of attempts at 10 second intervals.
        maxLoopTries = 15
        currentLoop = 1
        b_checkAgain = True
        while b_checkAgain:
            str_responseStatus = plg_inst_manager.check_plugin_instance_app_exec_status()
            if str_responseStatus == 'finishedSuccessfully':
                b_checkAgain = False
            elif currentLoop < maxLoopTries:
                time.sleep(10)
            if currentLoop == maxLoopTries:
                b_checkAgain = False
            currentLoop += 1
        self.assertEqual(pl_inst.status, 'finishedSuccessfully')

        str_fileCreatedByPlugin = os.path.join(pl_inst.get_output_path(), 'out.txt')
        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # make sure str_fileCreatedByPlugin file was created in Swift storage
        object_list = conn.get_container(
            settings.SWIFT_CONTAINER_NAME,
            prefix=str_fileCreatedByPlugin,
            full_listing=True)[1]
        self.assertEqual(object_list[0]['name'], str_fileCreatedByPlugin)
