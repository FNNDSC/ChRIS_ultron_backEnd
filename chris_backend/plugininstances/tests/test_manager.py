
import logging
import os
import io
import time
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.conf import settings

from pfconclient import client as pfcon

from core.storage import connect_storage
from plugins.models import PluginMeta, Plugin
from plugins.models import PluginParameter
from plugininstances.models import PluginInstance, PathParameter, ComputeResource
from plugininstances.services import manager


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class PluginInstanceManagerTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.storage_manager = connect_storage(settings)

        self.plugin_fs_name = "simplefsapp"
        self.username = 'foo'
        self.password = 'foo-pass'

        plugin_parameters = [{'name': 'dir', 'type': 'path', 'action': 'store',
                              'optional': False, 'flag': '--dir', 'short_flag': '-d',
                              'help': 'test plugin', 'ui_exposed': True}]

        self.plg_data = {'description': 'A simple chris fs app demo',
                         'version': '0.1',
                         'dock_image': 'fnndsc/pl-simplefsapp',
                         'execshell': 'python3',
                         'selfpath': '/usr/local/bin',
                         'selfexec': 'simplefsapp'}

        self.plg_meta_data = {'name': self.plugin_fs_name,
                              'title': 'Dir plugin',
                              'license': 'MIT',
                              'type': 'fs',
                              'icon': 'http://github.com/plugin',
                              'category': 'Dir',
                              'stars': 0,
                              'authors': 'FNNDSC (dev@babyMRI.org)'}

        self.plugin_repr = self.plg_data.copy()
        self.plugin_repr.update(self.plg_meta_data)
        self.plugin_repr['parameters'] = plugin_parameters

        token = pfcon.Client.get_auth_token(COMPUTE_RESOURCE_URL + 'auth-token/', 'pfcon',
                                            'pfcon1234')
        pfcon_client = pfcon.Client(COMPUTE_RESOURCE_URL, token)
        pfcon_client.get_server_info()

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL, compute_user='pfcon',
            compute_password='pfcon1234', compute_innetwork=pfcon_client.pfcon_innetwork)

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

    def test_assemble_exec(self):
        self.assertListEqual(
            ['python', '/usr/local/src/script.py'],
            manager.PluginInstanceManager._assemble_exec('/usr/local/src', 'script.py', 'python')
        )
        self.assertListEqual(
            ['python', 'script.py'],
            manager.PluginInstanceManager._assemble_exec(None, 'script.py', 'python')
        )
        self.assertListEqual(
            ['rust_is_better_than_python'],
            manager.PluginInstanceManager._assemble_exec(None, 'rust_is_better_than_python', None)
        )

    def test_mananger_can_run_registered_plugin_app(self):
        """
        Test whether the manager can run an already registered plugin app.
        """
        with mock.patch.object(manager, 'json_zip2str',
                               return_value='raw') as json_zip2str_mock:
            user = User.objects.get(username=self.username)
            plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
            (pl_inst, tf) = PluginInstance.objects.get_or_create(
                plugin=plugin, owner=user, status='scheduled',
                compute_resource=plugin.compute_resources.all()[0])
            pl_param = plugin.parameters.all()[0]
            PathParameter.objects.get_or_create(plugin_inst=pl_inst,
                                                plugin_param=pl_param,
                                                value=self.username)
            plg_inst_manager = manager.PluginInstanceManager(pl_inst)
            plg_inst_manager.get_job_status_summary = mock.Mock(return_value='summary')
            plg_inst_manager.pfcon_client.submit_job = mock.Mock(
                return_value='dictionary')

            # call run_plugin_instance_app method
            plg_inst_manager.run_plugin_instance_app()

            self.assertEqual(pl_inst.status, 'started')
            self.assertEqual(pl_inst.summary, 'summary')
            self.assertEqual(pl_inst.raw, 'raw')
            plg_inst_manager.pfcon_client.submit_job.assert_called_once()
            plg_inst_manager.get_job_status_summary.assert_called_once()
            json_zip2str_mock.assert_called_once()

    def test_mananger_can_check_plugin_instance_app_exec_status(self):
        """
        Test whether the manager can check a plugin's app execution status
        """
        pass
        #    response_mock = mock.Mock()
        #    response_mock.status_code = 200
        #    with mock.patch.object(manager.requests, 'post',
        #                          return_value=response_mock) as post_mock:
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
        #     plg_inst_manager = manager.PluginInstanceManager(pl_inst)
        #     plg_inst_manager.check_plugin_instance_app_exec_status()
        #     self.assertEqual(pl_inst.status, 'started')
        #     msg = {
        #         "action": "status",
        #         "meta": {
        #             "remote": {
        #                 "key": plg_inst_manager.str_job_id
        #             }
        #         }
        #     }
        #     post_mock.assert_called_with(msg)

    @tag('integration', 'error-pman')
    def test_integration_mananger_can_run_and_check_plugin_instance_app_exec_status(self):
        """
        Test whether the manager can check a plugin's app execution status.
        """
        # upload a file to the storage user's space
        user_space_path = '%s/uploads/' % self.username
        with io.StringIO('Test file') as f:
            self.storage_manager.upload_obj(user_space_path + 'test.txt', f.read(),
                                          content_type='text/plain')

        # create a plugin's instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, status='scheduled',
            compute_resource=plugin.compute_resources.all()[0])
        pl_param = plugin.parameters.all()[0]
        PathParameter.objects.get_or_create(plugin_inst=pl_inst, plugin_param=pl_param,
                                            value=user_space_path)

        # run the plugin instance
        plg_inst_manager = manager.PluginInstanceManager(pl_inst)
        plg_inst_manager.run_plugin_instance_app()
        self.assertEqual(pl_inst.status, 'started')

        # In the following we keep checking the status until the job ends with
        # 'finishedSuccessfully'. The code runs in a lazy loop poll with a
        # max number of attempts at 10 second intervals.
        maxLoopTries = 10
        currentLoop = 1
        b_checkAgain = True
        time.sleep(10)
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
        # make sure str_fileCreatedByPlugin file was created in storage
        self.assertTrue(self.storage_manager.obj_exists(str_fileCreatedByPlugin))

        # delete files from storage
        self.storage_manager.delete_obj(user_space_path + 'test.txt')
        # obj_paths = self.storage_manager.ls(pl_inst.get_output_path())
        # for path in obj_paths:
        #     self.storage_manager.delete_obj(path)
