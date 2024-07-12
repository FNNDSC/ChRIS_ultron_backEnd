
import logging
from unittest import mock, skip

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.conf import settings

from plugins.models import PluginMeta, Plugin, ComputeResource
from plugininstances.models import PluginInstance

from plugininstances import tasks


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL
CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class TasksTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.username = 'foo'
        self.password = 'bar'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL, compute_user='pfcon',
            compute_password='pfcon1234')

        # create the chris user
        User.objects.create_user(username=self.username, password=self.password)

        # create two plugins
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin_fs, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_fs.compute_resources.set([self.compute_resource])
        plugin_fs.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_convert', type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class PluginInstanceTasksTests(TasksTests):
    """
    Test the plugin instance tasks.
    """

    def setUp(self):
        super(PluginInstanceTasksTests, self).setUp()
        plugin = Plugin.objects.get(meta__name="pacspull")
        # create a plugin's instance
        user = User.objects.get(username=self.username)
        (self.plg_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin,
            owner=user,
            compute_resource=plugin.compute_resources.all()[0])
        self.plg_inst.status = 'started'
        self.plg_inst.save()

    def test_task_run_plugin_instance(self):
        with mock.patch.object(tasks.PluginInstanceManager, 'run_plugin_instance_app',
                               return_value=None) as run_mock:
            tasks.run_plugin_instance(self.plg_inst.id)
            run_mock.assert_called_with()

    def test_task_check_plugin_instance_exec_status(self):
        with mock.patch.object(tasks.PluginInstanceManager,
                               'check_plugin_instance_app_exec_status',
                               return_value=None) as check_exec_status_mock:
            tasks.check_plugin_instance_exec_status(self.plg_inst.id)
            check_exec_status_mock.assert_called_with()

    def test_task_cancel_plugin_instance(self):
        with mock.patch.object(tasks.PluginInstanceManager,
                               'cancel_plugin_instance_app_exec',
                               return_value=None) as cancel_mock:
            tasks.cancel_plugin_instance(self.plg_inst.id)
            cancel_mock.assert_called_with()

    def test_task_check_started_plugin_instances_exec_status(self):
        with mock.patch.object(tasks.check_plugin_instance_exec_status, 'delay',
                               return_value=None) as delay_mock:
            tasks.check_started_plugin_instances_exec_status()

            # check that the check_plugin_instance_exec_status task was called with appropriate args
            delay_mock.assert_called_with(self.plg_inst.id)
            self.assertEqual(self.plg_inst.status, 'started')
