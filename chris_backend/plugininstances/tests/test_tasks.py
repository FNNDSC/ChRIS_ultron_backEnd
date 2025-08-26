
import logging
import time
from datetime import timedelta
from unittest import mock, skip

from django.test import TestCase, TransactionTestCase, tag
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

from celery.contrib.testing.worker import start_worker
from core.celery import app as celery_app
from core.celery import task_routes

from plugins.models import PluginMeta, Plugin, ComputeResource
from plugininstances.models import PluginInstance, PluginInstanceLock

from plugininstances import tasks


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL
CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class TasksTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # superuser chris (owner of root folders)
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


class TasksAsyncTests(TransactionTestCase):

    @classmethod
    def setUpClass(cls):
        logging.disable(logging.WARNING)
        super().setUpClass()
        # route tasks to this worker by using the default 'celery' queue
        # that is exclusively used for the automated tests
        celery_app.conf.update(task_routes=None)
        cls.celery_worker = start_worker(celery_app,
                                         concurrency=1,
                                         perform_ping_check=False)
        cls.celery_worker.__enter__()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.celery_worker.__exit__(None, None, None)
        # reset routes to the original queues
        celery_app.conf.update(task_routes=task_routes)
        logging.disable(logging.NOTSET)

    def setUp(self):
        # superuser chris (owner of root folders)
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


class PluginInstanceAsyncTasksTests(TasksAsyncTests):
    """
    Test the plugin instance tasks when running async in the worker.
    """

    def setUp(self):
        super(PluginInstanceAsyncTasksTests, self).setUp()

        plugin = Plugin.objects.get(meta__name="pacspull")
        # create a plugin's instance
        user = User.objects.get(username=self.username)
        (self.plg_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin,
            owner=user,
            compute_resource=plugin.compute_resources.all()[0])
        self.plg_inst.status = 'started'
        self.plg_inst.save()

    @tag('integration')
    def test_task_run_plugin_instance_triggers_cancelling_when_exception_raised_during_async_run(self):
        with mock.patch.object(tasks.PluginInstanceManager,'delete_plugin_instance_job_from_remote',
                               return_value=None) as delete_remote_job_mock:
            with mock.patch.object(tasks.PluginInstanceManager, 'run_plugin_instance_app',
                                   side_effect=Exception):
                with mock.patch("logging.Logger._log"):  # disable the error logging
                    tasks.run_plugin_instance.delay(self.plg_inst.id)

                    for _ in range(10):
                        time.sleep(3)
                        self.plg_inst.refresh_from_db()
                        if self.plg_inst.status == 'cancelled': break

                    self.assertEqual(self.plg_inst.status, 'cancelled')  # instance must be cancelled
                    delete_remote_job_mock.assert_called_with()

    @tag('integration')
    def test_task_check_plugin_instance_exec_status_triggers_cancelling_when_exception_raised_during_async_run(self):
        with mock.patch.object(tasks.PluginInstanceManager,'delete_plugin_instance_job_from_remote',
                               return_value=None) as delete_remote_job_mock:
            with mock.patch.object(tasks.PluginInstanceManager, 'check_plugin_instance_app_exec_status',
                                   side_effect=Exception):
                with mock.patch("logging.Logger._log"):  # disable the error logging
                    tasks.check_plugin_instance_exec_status.delay(self.plg_inst.id)

                    for _ in range(10):
                        time.sleep(3)
                        self.plg_inst.refresh_from_db()
                        if self.plg_inst.status == 'cancelled': break

                    self.assertEqual(self.plg_inst.status, 'cancelled')  # instance must be cancelled
                    delete_remote_job_mock.assert_called_with()

    @tag('integration')
    def test_task_cancel_plugin_instance_triggers_cancelling_when_exception_raised_during_async_run(self):
        with mock.patch.object(tasks.PluginInstanceManager,'delete_plugin_instance_job_from_remote',
                               return_value=None) as delete_remote_job_mock:
            with mock.patch.object(tasks.PluginInstanceManager, 'cancel_plugin_instance_app_exec',
                                side_effect=Exception):
                with mock.patch("logging.Logger._log"):  # disable the error logging
                    tasks.cancel_plugin_instance.delay(self.plg_inst.id)

            for _ in range(10):
                time.sleep(3)
                self.plg_inst.refresh_from_db()
                if self.plg_inst.status == 'cancelled': break

            self.assertEqual(self.plg_inst.status, 'cancelled')  # instance must be cancelled
            delete_remote_job_mock.assert_called_with()

    @tag('integration')
    def test_task_cancel_plugin_instances_stuck_in_lock_during_async_run(self):
        self.plg_inst.status = 'registeringFiles'
        self.plg_inst.save(update_fields=['status'])

        plg_inst_lock = PluginInstanceLock(plugin_inst=self.plg_inst)
        plg_inst_lock.save()
        plg_inst_lock.start_date = timezone.now() - timedelta(minutes=241)  # hardcoded cutoff delta in tasks.py
        plg_inst_lock.save(update_fields=['start_date'])

        with mock.patch.object(tasks.PluginInstanceManager,'delete_plugin_instance_job_from_remote',
                               return_value=None) as delete_remote_job_mock:
            tasks.cancel_plugin_instances_stuck_in_lock.delay()

            for _ in range(10):
                time.sleep(3)
                self.plg_inst.refresh_from_db()
                if self.plg_inst.status == 'cancelled': break

            self.assertEqual(self.plg_inst.status, 'cancelled')  # instance must be cancelled
            delete_remote_job_mock.assert_called_with()
