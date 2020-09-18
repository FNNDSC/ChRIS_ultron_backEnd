
import logging
from unittest import mock, skip

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.conf import settings

from plugins.models import PluginMeta, Plugin, ComputeResource
from plugininstances.models import PluginInstance

from plugininstances import tasks


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class TasksTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.username = 'foo'
        self.password = 'bar'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

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

    def test_task_run_plugin_instance(self):
        with mock.patch.object(tasks.PluginInstance, 'run',
                               return_value=None) as run_mock:
            tasks.run_plugin_instance(self.plg_inst.id)
            run_mock.assert_called_with()

    def test_task_check_plugin_instance_exec_status(self):
        with mock.patch.object(tasks.PluginInstance, 'check_exec_status',
                               return_value=None) as check_exec_status_mock:
            tasks.check_plugin_instance_exec_status(self.plg_inst.id)
            check_exec_status_mock.assert_called_with()

    def test_task_check_scheduled_plugin_instances_exec_status(self):
        with mock.patch.object(tasks.check_plugin_instance_exec_status, 'delay',
                               return_value=None) as delay_mock:
            tasks.check_scheduled_plugin_instances_exec_status()

            # check that the check_plugin_instance_exec_status task was called with appropriate args
            delay_mock.assert_called_with(self.plg_inst.id)
            self.assertEqual(self.plg_inst.status, 'started')

        # create mri_convert ds plugin instance
        previous_plg_inst = self.plg_inst
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name="mri_convert")
        (plg_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, previous=previous_plg_inst,
            compute_resource=plugin.compute_resources.all()[0])

        plg_inst.status = 'waitingForPrevious'
        plg_inst.save()
        previous_plg_inst.status = 'finishedSuccessfully'
        previous_plg_inst.save()
        with mock.patch.object(tasks.check_plugin_instance_exec_status, 'delay',
                               return_value=None) as check_status_delay_mock:
            with mock.patch.object(tasks.run_plugin_instance, 'delay',
                                   return_value=None) as run_delay_mock:
                tasks.check_scheduled_plugin_instances_exec_status()
                plg_inst.refresh_from_db()
                self.assertEqual(plg_inst.status, 'started')

                # check that the check_plugin_instance_exec_status task was not called
                check_status_delay_mock.assert_not_called()
                # check that the run_plugin_instance task was called with appropriate args
                run_delay_mock.assert_called_with(plg_inst.id)

        plg_inst.status = 'waitingForPrevious'
        plg_inst.save()
        previous_plg_inst.status = 'finishedWithError'
        previous_plg_inst.save()
        with mock.patch.object(tasks.check_plugin_instance_exec_status, 'delay',
                               return_value=None) as check_status_delay_mock:
            with mock.patch.object(tasks.run_plugin_instance, 'delay',
                                   return_value=None) as run_delay_mock:
                tasks.check_scheduled_plugin_instances_exec_status()
                plg_inst.refresh_from_db()
                self.assertEqual(plg_inst.status, 'cancelled')

                # check that the check_plugin_instance_exec_status task was not called
                check_status_delay_mock.assert_not_called()
                # check that the run_plugin_instance task was not called
                run_delay_mock.assert_not_called()
