"""
Abstract job manager module that provides the base interface for submitting 
and checking the execution status of jobs running in a remote compute 
environment (ChRIS / pfcon interface) as well as deleting them when finished.
"""

import logging
import io
import abc

from pfconclient import client as pfcon
from pfconclient.client import JobType
from pfconclient.exceptions import (PfconRequestException,
                                    PfconRequestInvalidTokenException)

from django.conf import settings
from django.utils import timezone

from core.storage import connect_storage
from core.models import ChrisInstance


logger = logging.getLogger(__name__)


class PluginInstanceJob(abc.ABC):
    """
    ``PluginInstanceJob`` provides an interface for managing remote jobs related to a 
    plugin instance.

    ``PluginInstanceJob`` methods implement helper functions for submitting and checking 
    the status of jobs required during the full flow of running a plugin instance's app 
    on a remote compute environment.
    """

    def __init__(self, plugin_instance: ChrisInstance):

        self.c_plugin_inst = plugin_instance

        self.str_job_id_prefix = ChrisInstance.load().job_id_prefix
        self.str_job_id = self.str_job_id_prefix + str(plugin_instance.id)

        cr = self.c_plugin_inst.compute_resource
        self.pfcon_client = pfcon.Client(cr.compute_url, cr.compute_auth_token)
        self.pfcon_client.pfcon_innetwork = cr.compute_innetwork
        self.pfcon_client.requires_copy_job = cr.compute_requires_copy_job
        self.pfcon_client.requires_upload_job = cr.compute_requires_upload_job

        self.plugin_inst_output_files = set()  # set of obj names in object storage

        self.storage_manager = connect_storage(settings)
        self.storage_env = settings.STORAGE_ENV

    @abc.abstractmethod
    def run(self):
        """
        Submit the job to the remote compute service for execution.
        """
        ...

    @abc.abstractmethod
    def check_exec_status(self):
        """
        Check the job's execution status in the remote compute service.
        """
        ...
 
    @abc.abstractmethod
    def cancel_exec(self):
        """
        Cancel the job's execution. It connects to the remote compute service
        to cancel the job.
        """
        ...

    @abc.abstractmethod
    def delete(self):
        """
        Delete the job from the remote compute. It connects to the
        remote compute service to delete the job.
        """
        ...

    @abc.abstractmethod
    def handle_finished_successfully_status(self):
        """
        Handle the 'finishedSuccessfully' status returned by the remote compute.
        """
        ...

    @abc.abstractmethod
    def handle_finished_with_error_status(self):
        """
        Handle the 'finishedWithError' status returned by the remote compute.
        """
        ...

    @abc.abstractmethod
    def handle_undefined_status(self):
        """
        Handle the 'undefined' status returned by the remote compute.
        """
        ...

    def get_job_status_summary(self, d_resp: dict | None = None, 
                               push_path_status: bool | None = None, 
                               pull_path_status: bool | None = None) -> dict:
        """
        Get a job status JSON summary from pfcon response.
        """
        d_jobStatusSummary = self.c_plugin_inst.summary

        if push_path_status is not None:
            d_jobStatusSummary['pushPath']['status'] = push_path_status

        if pull_path_status is not None:
            d_jobStatusSummary['pullPath']['status'] = pull_path_status

        if d_resp is not None:
            d_c = d_resp['compute']

            if d_c['status'] in ('undefined', 'finishedSuccessfully',
                                'finishedWithError'):
                d_jobStatusSummary['compute']['return']['status'] = True

            d_jobStatusSummary['compute']['return']['job_status'] = d_c['status']
            logs = d_jobStatusSummary['compute']['return']['job_logs'] = d_c['logs']

            # truncate logs, assuming worst case where every character needs
            # to be escaped
            if len(logs) > 1800:
                d_jobStatusSummary['compute']['return']['job_logs'] = logs[-1800:]
        return d_jobStatusSummary

    def schedule_remote_cleanup(self):
        """
        Schedule a remote cleanup operation to delete storeBase data and all containers
        from the remote compute environment. This sets the remote_cleanup_status to
        'deletingData' and schedules a PluginInstanceDeleteJob celery task.
        """
        from plugininstances.tasks import run_plugin_instance_job

        job_id = self.str_job_id
        logger.info(f'Scheduling remote cleanup for job {job_id}')

        self.c_plugin_inst.remote_cleanup_status = 'deletingData'
        self.c_plugin_inst.remote_cleanup_retry_count = 0
        self.c_plugin_inst.save(update_fields=['remote_cleanup_status',
                                               'remote_cleanup_retry_count'])
        run_plugin_instance_job.delay(self.c_plugin_inst.id,
                                      'PluginInstanceDeleteJob')

    def delete_all_remote_containers(self) -> bool:
        """
        Delete all remote containers (copy, plugin, upload, delete) for this plugin
        instance's job from the remote compute environment. Returns True if all
        deletions succeeded, False if any failed.
        """
        job_id = self.str_job_id
        cr = self.c_plugin_inst.compute_resource
        all_succeeded = True
        job_types = []

        if cr.compute_requires_copy_job:
            job_types.append(JobType.COPY)

        job_types.append(JobType.PLUGIN)

        if cr.compute_requires_upload_job:
            job_types.append(JobType.UPLOAD)
            
        job_types.append(JobType.DELETE)

        for job_type in job_types:
            try:
                self._delete(job_type, job_id)
            except PfconRequestException:
                logger.error(f'[CODE12,{job_id}]: Error deleting {job_type} container '
                             f'from pfcon at url -->{self.pfcon_client.url}<--')
                all_succeeded = False
        return all_succeeded
    
    def _refresh_compute_resource_auth_token(self):
        """
        Get a new auth token from a remote pfcon service and update the DB.
        """
        cr = self.c_plugin_inst.compute_resource
        token = pfcon.Client.get_auth_token(cr.compute_auth_url, cr.compute_user,
                                            cr.compute_password)
        self.pfcon_client.set_auth_token(token)
        cr.compute_auth_token = token
        cr.save()

    def _submit(self, job_type: JobType, job_id: str, job_descriptors: dict, 
                dfile: io.BytesIO | None = None, timeout: int = 200) -> dict:
        """
        Submit job to a remote pfcon service.
        """
        try:
            d_resp = self.pfcon_client.submit_job(job_type, job_id, job_descriptors, 
                                                  dfile, timeout)
        except PfconRequestInvalidTokenException:
            logger.info(f'Auth token has expired while submitting {job_type} job '
                        f'{job_id} to pfcon url -->{self.pfcon_client.url}<--')
            self._refresh_compute_resource_auth_token()
            d_resp = self.pfcon_client.submit_job(job_type, job_id, job_descriptors, 
                                                  dfile, timeout)
        except PfconRequestException:
            if self.pfcon_client.requires_copy_job:
                raise
            else:  # legacy behavior
                # FIXME HACK
                # Under some conditions, the requests library will produce a
                # "Connection Aborted" error instead of a 401 response. This happens when
                # pfcon responds eagerly to an invalid token and closes the connection.
                # The temporary workaround is to catch a wider range of Exceptions here.
                # Ideally we only want to try again in the event that we know the token is
                # invalid, PfconRequestInvalidTokenException, however this exception
                # is not correctly raised in all the situations where it should be.
                #
                logger.exception(f'Error while submitting {job_type} job {job_id} to pfcon '
                                f'url -->{self.pfcon_client.url}<--, auth token might have '
                                f'expired, will try refreshing token and resubmitting job')
                self._refresh_compute_resource_auth_token()
                d_resp = self.pfcon_client.submit_job(job_type, job_id, job_descriptors, 
                                                    dfile, timeout)
        return d_resp

    def _get_status(self, job_type: JobType, job_id: str, timeout: int = 100) -> dict:
        """
        Get job status from a remote pfcon service.
        """
        try:
            d_resp = self.pfcon_client.get_job_status(job_type, job_id, timeout)
        except PfconRequestInvalidTokenException:
            logger.info(f'Auth token has expired while getting status for {job_type} job '
                        f'{job_id} from pfcon url -->{self.pfcon_client.url}<--')
            self._refresh_compute_resource_auth_token()
            d_resp = self.pfcon_client.get_job_status(job_type, job_id, timeout)
        except PfconRequestException:
            if self.pfcon_client.requires_copy_job:
                raise
            else:  # legacy behavior
                # FIXME HACK
                # Same as in above method.
                #
                logger.exception(f'Error while getting status for {job_type} job {job_id} '
                                f'from pfcon url -->{self.pfcon_client.url}<--, auth token '
                                f'might have expired, will try refreshing token and '
                                f'resubmitting job status request')
                self._refresh_compute_resource_auth_token()
                d_resp = self.pfcon_client.get_job_status(job_type, job_id, timeout)
        return d_resp

    def _delete(self, job_type: JobType, job_id: str, timeout: int = 200):
        """
        Delete a job from a remote pfcon service.
        """
        try:
            self.pfcon_client.delete_job(job_type, job_id, timeout)
        except PfconRequestInvalidTokenException:
            logger.info(f'Auth token has expired while requesting to delete {job_type} '
                        f'job {job_id} from pfcon url -->{self.pfcon_client.url}<--')
            self._refresh_compute_resource_auth_token()
            self.pfcon_client.delete_job(job_type, job_id, timeout)
        except PfconRequestException:
            if self.pfcon_client.requires_copy_job:
                raise
            else:  # legacy behavior
                # FIXME HACK (for legacy storage)
                # Same as in above method.
                #
                logger.exception(f'Error while requesting to delete {job_type} job {job_id} '
                                f'from pfcon url -->{self.pfcon_client.url}<--, auth token '
                                f'might have expired, will try refreshing token and '
                                f'resubmitting job delete request')
                self._refresh_compute_resource_auth_token()
                self.pfcon_client.delete_job(job_type, job_id, timeout)

    def _job_has_timeout(self) -> bool:
        """
        Check if a job has timed out. If the associated job's execution time exceeds
        the maximum set for the remote compute environment then the job has timed out.
        """
        max_job_exec_sec = self.c_plugin_inst.compute_resource.max_job_exec_seconds

        if max_job_exec_sec >= 0:
            delta_exec_time = timezone.now() - self.c_plugin_inst.start_date
            delta_seconds = delta_exec_time.total_seconds()

            if delta_seconds > max_job_exec_sec:
                return True
        return False
