
import logging
import io
import time
import uuid
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User, Group
from django.conf import settings

from pfconclient import client as pfcon
from pfconclient.client import JobType
from pfconclient.exceptions import PfconRequestException

from core.models import ChrisInstance, ChrisFolder
from core.storage import connect_storage
from plugins.models import PluginMeta, Plugin
from plugins.models import PluginParameter
from plugininstances.models import PluginInstance, PathParameter, ComputeResource
from plugininstances.services import deletejobs
from plugininstances.services.copyjobs import PluginInstanceCopyJob
from plugininstances.services.pluginjobs import PluginInstanceAppJob
from plugininstances.services.uploadjobs import PluginInstanceUploadJob


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL
CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class PluginInstanceDeleteJobTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)
        logging.getLogger('plugininstances.services.deletejobs').setLevel(logging.CRITICAL)

        # use a unique job_id_prefix to avoid pfcon job ID collisions with
        # stale jobs from prior test runs
        chris_inst = ChrisInstance.load()
        chris_inst.job_id_prefix = f'test-{uuid.uuid4().hex[:8]}-'
        chris_inst.save(update_fields=['job_id_prefix'])

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.storage_manager = connect_storage(settings)

        self.plugin_fs_name = 'simplefsapp'
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

        (self.compute_resource, tf) = ComputeResource.objects.update_or_create(
            name='host',
            defaults={'compute_url': COMPUTE_RESOURCE_URL, 'compute_user': 'pfcon',
                      'compute_password': 'pfcon1234',
                      'compute_innetwork': pfcon_client.pfcon_innetwork,
                      'compute_requires_copy_job': True,
                      'compute_requires_upload_job': pfcon_client.pfcon_innetwork and settings.STORAGE_ENV == 'swift'})

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
        logging.getLogger('plugininstances.services.deletejobs').setLevel(logging.NOTSET)

    def test_run_success(self):
        with mock.patch.object(deletejobs, 'json_zip2str',
                               return_value='raw') as json_zip2str_mock:
            user = User.objects.get(username=self.username)
            plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
            (pl_inst, tf) = PluginInstance.objects.get_or_create(
                plugin=plugin, owner=user, status='finishedSuccessfully',
                compute_resource=plugin.compute_resources.all()[0])
            pl_inst.remote_cleanup_status = 'deletingData'
            pl_inst.save(update_fields=['remote_cleanup_status'])
            delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
            delete_job.get_job_status_summary = mock.Mock(return_value='summary')
            delete_job.pfcon_client.submit_job = mock.Mock(return_value='dictionary')

            delete_job.run()

            self.assertEqual(pl_inst.summary, 'summary')
            self.assertEqual(pl_inst.raw, 'raw')
            delete_job.pfcon_client.submit_job.assert_called_once()
            json_zip2str_mock.assert_called_once()

    def test_run_skips_when_not_deleting_data(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'complete'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.pfcon_client.submit_job = mock.Mock()

        delete_job.run()

        delete_job.pfcon_client.submit_job.assert_not_called()

    def test_run_pfcon_error_increments_retry(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.remote_cleanup_retry_count = 0
        pl_inst.save(update_fields=['remote_cleanup_status', 'remote_cleanup_retry_count'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.pfcon_client.submit_job = mock.Mock(side_effect=PfconRequestException('test error'))
        delete_job._increment_retry_or_fail = mock.Mock()

        delete_job.run()

        delete_job._increment_retry_or_fail.assert_called_once()

    def test_check_exec_status_finished_successfully(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._get_status = mock.Mock(
            return_value={'compute': {'status': 'finishedSuccessfully', 'logs': ''}})
        delete_job.handle_finished_successfully_status = mock.Mock()

        delete_job.check_exec_status()

        delete_job.handle_finished_successfully_status.assert_called_once()

    def test_check_exec_status_finished_with_error(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._get_status = mock.Mock(
            return_value={'compute': {'status': 'finishedWithError', 'logs': ''}})
        delete_job.handle_finished_with_error_status = mock.Mock()

        delete_job.check_exec_status()

        delete_job.handle_finished_with_error_status.assert_called_once()

    def test_check_exec_status_undefined(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._get_status = mock.Mock(
            return_value={'compute': {'status': 'undefined', 'logs': ''}})
        delete_job.handle_undefined_status = mock.Mock()

        delete_job.check_exec_status()

        delete_job.handle_undefined_status.assert_called_once()

    def test_check_exec_status_skips_when_not_deleting_data(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'complete'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._get_status = mock.Mock()

        result = delete_job.check_exec_status()

        delete_job._get_status.assert_not_called()
        self.assertEqual(result, 'complete')

    def test_check_exec_status_pfcon_error_resubmits(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._get_status = mock.Mock(side_effect=PfconRequestException('test error'))
        delete_job.run = mock.Mock()

        delete_job.check_exec_status()

        delete_job.run.assert_called_once()

    def test_cancel_exec(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        original_status = pl_inst.status
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)

        delete_job.cancel_exec()

        self.assertEqual(pl_inst.remote_cleanup_status, 'failed')
        self.assertEqual(pl_inst.status, original_status)  # status must NOT be modified

    def test_delete_success(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._delete = mock.Mock()

        delete_job.delete()

        delete_job._delete.assert_called_once_with(JobType.DELETE, delete_job.str_job_id)
        self.assertNotEqual(pl_inst.error_code, 'CODE12')

    def test_delete_error(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._delete = mock.Mock(side_effect=PfconRequestException('test error'))

        delete_job.delete()

        self.assertEqual(pl_inst.error_code, 'CODE12')

    def test_handle_finished_successfully_status(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.delete_all_remote_containers = mock.Mock(return_value=True)
        delete_job.save_plugin_instance_final_status = mock.Mock()

        delete_job.handle_finished_successfully_status()

        self.assertEqual(pl_inst.remote_cleanup_status, 'complete')
        delete_job.save_plugin_instance_final_status.assert_called_once()

    def test_handle_finished_successfully_status_cancelled_cleans_output(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='cancelled',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.delete_all_remote_containers = mock.Mock(return_value=True)
        delete_job._cleanup_plugin_instance_output_dir = mock.Mock()
        delete_job.save_plugin_instance_final_status = mock.Mock()

        delete_job.handle_finished_successfully_status()

        delete_job._cleanup_plugin_instance_output_dir.assert_called_once()

    def test_handle_finished_successfully_status_container_delete_fails(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.delete_all_remote_containers = mock.Mock(return_value=False)

        delete_job.handle_finished_successfully_status()

        self.assertEqual(pl_inst.remote_cleanup_status, 'deletingContainers')

    def test_handle_finished_with_error_status(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._increment_retry_or_fail = mock.Mock()

        delete_job.handle_finished_with_error_status()

        delete_job._increment_retry_or_fail.assert_called_once()

    def test_handle_undefined_status(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.save(update_fields=['remote_cleanup_status'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._increment_retry_or_fail = mock.Mock()

        delete_job.handle_undefined_status()

        delete_job._increment_retry_or_fail.assert_called_once()

    def test_increment_retry_or_fail_retries(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.remote_cleanup_retry_count = 0
        pl_inst.save(update_fields=['remote_cleanup_status', 'remote_cleanup_retry_count'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.run = mock.Mock()

        delete_job._increment_retry_or_fail()

        self.assertEqual(pl_inst.remote_cleanup_retry_count, 1)
        delete_job.run.assert_called_once()

    def test_increment_retry_or_fail_gives_up(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.remote_cleanup_retry_count = PluginInstance.MAX_REMOTE_CLEANUP_RETRIES + 1
        pl_inst.save(update_fields=['remote_cleanup_status', 'remote_cleanup_retry_count'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.save_plugin_instance_final_status = mock.Mock()

        delete_job._increment_retry_or_fail()

        self.assertEqual(pl_inst.remote_cleanup_status, 'failed')
        delete_job.save_plugin_instance_final_status.assert_called_once()

    def test_increment_retry_or_fail_cancelled_cleans_output(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='cancelled',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.remote_cleanup_status = 'deletingData'
        pl_inst.remote_cleanup_retry_count = PluginInstance.MAX_REMOTE_CLEANUP_RETRIES + 1
        pl_inst.save(update_fields=['remote_cleanup_status', 'remote_cleanup_retry_count'])
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._cleanup_plugin_instance_output_dir = mock.Mock()
        delete_job.save_plugin_instance_final_status = mock.Mock()

        delete_job._increment_retry_or_fail()

        delete_job._cleanup_plugin_instance_output_dir.assert_called_once()

    def test_save_plugin_instance_final_status(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='finishedSuccessfully',
            compute_resource=plugin.compute_resources.all()[0])

        # add a shared user and a shared group to the feed
        other_user = User.objects.create_user(username='other', password='other-pass')
        pl_inst.feed.shared_users.add(other_user)
        group = Group.objects.create(name='test-group')
        pl_inst.feed.shared_groups.add(group)

        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)

        with mock.patch.object(ChrisFolder, 'grant_group_permission') as mock_ggp, \
             mock.patch.object(ChrisFolder, 'grant_user_permission') as mock_gup, \
             mock.patch.object(ChrisFolder, 'grant_public_access') as mock_gpa:
            delete_job.save_plugin_instance_final_status()

            mock_ggp.assert_called_once_with(group, 'w')
            mock_gup.assert_called_once_with(other_user, 'w')
            mock_gpa.assert_not_called()  # feed.public is False by default

    def test_cleanup_plugin_instance_output_dir(self):
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='cancelled',
            compute_resource=plugin.compute_resources.all()[0])

        # create a child folder under the output folder
        child_folder = ChrisFolder(
            path=pl_inst.output_folder.path + '/subdir', owner=user)
        child_folder.save()

        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.storage_manager.delete_path = mock.Mock()

        delete_job._cleanup_plugin_instance_output_dir()

        self.assertFalse(ChrisFolder.objects.filter(pk=child_folder.pk).exists())
        delete_job.storage_manager.delete_path.assert_called_once_with(
            pl_inst.output_folder.path)

    @tag('integration')
    def test_integration_cleanup_plugin_instance_output_dir(self):
        user = User.objects.get(username=self.username)

        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, status='cancelled',
            compute_resource=plugin.compute_resources.all()[0])

        # upload a file to the plugin instance output folder and create a child folder, 
        # then check that they are deleted by _cleanup_plugin_instance_output_dir
        output_path = pl_inst.output_folder.path

        with io.StringIO('Test file') as f:
            self.storage_manager.upload_obj(output_path + '/test.txt', f.read(),
                                          content_type='text/plain')
        child_folder = ChrisFolder(
            path=output_path + '/subdir', owner=user)
        child_folder.save()

        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job._cleanup_plugin_instance_output_dir()

        self.assertFalse(ChrisFolder.objects.filter(pk=child_folder.pk).exists())
        self.assertFalse(self.storage_manager.obj_exists(output_path + '/test.txt'))

    @tag('integration')
    def test_integration_delete_job_can_run_and_check_exec_status(self):
        """
        Test whether the delete job can run and check execution status until cleanup
        completes.
        """
        # upload a file to the user's storage space and run through the full
        # copy job + app job flow until finishedSuccessfully
        user_space_path = f'home/{self.username}/uploads/'
        with io.StringIO('Test file') as f:
            self.storage_manager.upload_obj(user_space_path + 'test.txt', f.read(),
                                            content_type='text/plain')

        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, status='copying',
            compute_resource=plugin.compute_resources.all()[0])
        pl_param = plugin.parameters.all()[0]
        PathParameter.objects.get_or_create(plugin_inst=pl_inst, plugin_param=pl_param,
                                            value=user_space_path)

        self._run_to_finished_successfully(pl_inst)

        # at this point remote_cleanup_status is already 'deletingData' (set by
        # schedule_remote_cleanup() which was called at the end of the app job)
        self.assertEqual(pl_inst.remote_cleanup_status, 'deletingData')

        # run the delete job
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.run()

        # poll delete job status until cleanup completes
        maxLoopTries = 10
        currentLoop = 1
        time.sleep(5)
        while currentLoop <= maxLoopTries:
            delete_job.check_exec_status()
            if pl_inst.remote_cleanup_status != 'deletingData':
                break
            time.sleep(5)
            currentLoop += 1
        self.assertEqual(pl_inst.remote_cleanup_status, 'complete')

        # delete remaining files from storage
        self.storage_manager.delete_obj(user_space_path + 'test.txt')

    @tag('integration')
    def test_integration_delete_job_cancel_exec(self):
        """
        Test whether the delete job can be cancelled after submission.
        """
        # run through the full copy job + app job flow until finishedSuccessfully
        user_space_path = f'home/{self.username}/uploads/'
        with io.StringIO('Test file') as f:
            self.storage_manager.upload_obj(user_space_path + 'test.txt', f.read(),
                                            content_type='text/plain')

        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, status='copying',
            compute_resource=plugin.compute_resources.all()[0])
        pl_param = plugin.parameters.all()[0]
        PathParameter.objects.get_or_create(plugin_inst=pl_inst, plugin_param=pl_param,
                                            value=user_space_path)

        self._run_to_finished_successfully(pl_inst)

        # run the delete job then cancel it
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.run()
        delete_job.cancel_exec()

        self.assertEqual(pl_inst.remote_cleanup_status, 'failed')
        self.assertEqual(pl_inst.status, 'finishedSuccessfully')  # must NOT be modified

        # delete remaining files from storage
        self.storage_manager.delete_path(pl_inst.output_folder.path)
        self.storage_manager.delete_obj(user_space_path + 'test.txt')

    @tag('integration')
    def test_integration_delete_job_delete(self):
        """
        Test whether the delete job can be deleted from the remote compute after it
        finishes.
        """
        # run through the full copy job + app job flow until finishedSuccessfully
        user_space_path = f'home/{self.username}/uploads/'
        with io.StringIO('Test file') as f:
            self.storage_manager.upload_obj(user_space_path + 'test.txt', f.read(),
                                            content_type='text/plain')

        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, status='copying',
            compute_resource=plugin.compute_resources.all()[0])
        pl_param = plugin.parameters.all()[0]
        PathParameter.objects.get_or_create(plugin_inst=pl_inst, plugin_param=pl_param,
                                            value=user_space_path)

        self._run_to_finished_successfully(pl_inst)

        # run the delete job and poll until cleanup finishes
        delete_job = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job.run()
        maxLoopTries = 10
        currentLoop = 1
        time.sleep(5)
        while currentLoop <= maxLoopTries:
            delete_job.check_exec_status()
            if pl_inst.remote_cleanup_status != 'deletingData':
                break
            time.sleep(5)
            currentLoop += 1

        # delete the delete job container from pfcon
        delete_job2 = deletejobs.PluginInstanceDeleteJob(pl_inst)
        delete_job2.delete()

        self.assertNotEqual(pl_inst.error_code, 'CODE12')

        # delete remaining files from storage
        self.storage_manager.delete_obj(user_space_path + 'test.txt')

    def _run_to_finished_successfully(self, pl_inst):
        """
        Helper method to run through the full copy job + app job flow until the
        plugin instance reaches 'finishedSuccessfully' status.
        """
        # run the copy job
        copy_job = PluginInstanceCopyJob(pl_inst)
        copy_job.run()

        # poll copy job status until the copy finishes and the app job auto-starts
        maxLoopTries = 10
        currentLoop = 1
        time.sleep(5)
        while currentLoop <= maxLoopTries:
            copy_job.check_exec_status()
            if pl_inst.status == 'started':
                break
            time.sleep(5)
            currentLoop += 1
        if pl_inst.status == 'cancelled':
            self.skipTest('Copy job failed to transition to started - likely pfcon Docker issue')
        self.assertEqual(pl_inst.status, 'started')

        # poll app job status until it finishes or transitions to uploading
        app_job = PluginInstanceAppJob(pl_inst)
        maxLoopTries = 10
        currentLoop = 1
        b_checkAgain = True
        time.sleep(10)
        while b_checkAgain:
            str_responseStatus = app_job.check_exec_status()
            if str_responseStatus in ('finishedSuccessfully', 'uploading'):
                b_checkAgain = False
            elif currentLoop < maxLoopTries:
                time.sleep(10)
            if currentLoop == maxLoopTries:
                b_checkAgain = False
            currentLoop += 1

        # if compute_requires_upload_job=True the app job transitions to 'uploading';
        # poll the upload job until finishedSuccessfully
        if pl_inst.status == 'uploading':
            upload_job = PluginInstanceUploadJob(pl_inst)
            maxLoopTries = 10
            currentLoop = 1
            time.sleep(5)
            while currentLoop <= maxLoopTries:
                upload_job.check_exec_status()
                if pl_inst.status == 'finishedSuccessfully':
                    break
                time.sleep(10)
                currentLoop += 1

        self.assertEqual(pl_inst.status, 'finishedSuccessfully')
