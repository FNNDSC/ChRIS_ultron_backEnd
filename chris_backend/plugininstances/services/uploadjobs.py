"""
Upload job manager module that provides the interface for submitting and
checking the execution status of upload jobs running in a remote compute
environment (ChRIS / pfcon interface) as well as deleting them when finished.
"""

import logging
import json

from pfconclient.client import JobType
from pfconclient.exceptions import PfconRequestException

from django.utils import timezone
from django.db.utils import IntegrityError

from core.utils import json_zip2str
from plugininstances.models import PluginInstance, PluginInstanceLock
from .abstractjobs import PluginInstanceJob


logger = logging.getLogger(__name__)


class PluginInstanceUploadJob(PluginInstanceJob):
    """
    ``PluginInstanceUploadJob`` provides a concrete implementation for managing a remote
    upload job related to a plugin instance.
    """

    def run(self):
        """
        Run the plugin instance upload job via a call to a remote pfcon service.
        """
        if self.c_plugin_inst.status == 'cancelled':
            return

        job_id = self.str_job_id

        # create job description dictionary
        job_descriptors = {
            'cpu_limit': self.c_plugin_inst.cpu_limit,
            'memory_limit': self.c_plugin_inst.memory_limit,
            'job_output_path': self.c_plugin_inst.get_output_path()
        }

        pfcon_url = self.pfcon_client.url

        logger.info(f'Submitting upload job {job_id} to pfcon url -->{pfcon_url}<--, '
                    f'description: {json.dumps(job_descriptors, indent=4)}')
        try:
            d_resp = self._submit(JobType.UPLOAD, job_id, job_descriptors)
        except PfconRequestException as e:
            logger.error(f'[CODE01,{job_id}]: Error submitting upload job to pfcon url '
                         f'-->{pfcon_url}<--, detail: {str(e)}')

            self.c_plugin_inst.upload_retry_count += 1

            if self.c_plugin_inst.upload_retry_count > PluginInstance.MAX_UPLOAD_RETRIES:
                self.c_plugin_inst.error_code = 'CODE01'
                self.c_plugin_inst.status = 'cancelled'  # giving up 
                self.c_plugin_inst.save(update_fields=['status', 'error_code'])
                self.schedule_remote_cleanup()
            else:
                self.c_plugin_inst.save(update_fields=['upload_retry_count'])
                self.run()  # retry
        else:
            logger.info(f'Successfully submitted upload job {job_id} to pfcon url '
                        f'-->{pfcon_url}<--, response: {json.dumps(d_resp, indent=4)}')

            # update the job status and summary
            self.c_plugin_inst.summary = self.get_job_status_summary(d_resp)
            self.c_plugin_inst.raw = json_zip2str(d_resp)
            self.c_plugin_inst.save()

    def check_exec_status(self):
        """
        Check a plugin instance upload job's execution status. If the associated job's
        execution time exceeds the maximum set for the remote compute environment then
        the job is cancelled. Otherwise the job's execution status is fetched from the
        remote.
        """
        if self.c_plugin_inst.status == 'uploading':
            job_id = self.str_job_id

            if self._job_has_timeout():
                logger.error(f'[CODE13,{job_id}]: Error, upload job exceeded maximum '
                             f'execution time')
                self.c_plugin_inst.error_code = 'CODE13'
                self.cancel_exec()
                return self.c_plugin_inst.status

            pfcon_url = self.pfcon_client.url
            logger.info(f'Sending job status request to pfcon url -->{pfcon_url}<-- for '
                        f'upload job {job_id}')
            try:
                d_resp = self._get_status(JobType.UPLOAD, job_id)
            except PfconRequestException as e:
                logger.error(f'[CODE02,{job_id}]: Error getting upload job status at pfcon '
                             f'url -->{pfcon_url}<--, detail: {str(e)}')
                return self.c_plugin_inst.status  # return, periodic task will retry later

            logger.info(f'Successful job status response from pfcon url -->{pfcon_url}<--'
                        f' for upload job {job_id}: {json.dumps(d_resp, indent=4)}')

            status = d_resp['compute']['status']
            logger.info(f'Current upload job {job_id} remote status = {status}')
            logger.info(f'Current upload job {job_id} plugin instance DB status = '
                        f'{self.c_plugin_inst.status}')

            summary = self.get_job_status_summary(d_resp)
            self.c_plugin_inst.summary = summary
            raw = json_zip2str(d_resp)
            self.c_plugin_inst.raw = raw

            # only update (atomically) if still in upload phase to avoid concurrency problems
            PluginInstance.objects.filter(
                id=self.c_plugin_inst.id,
                status=self.c_plugin_inst.status).update(summary=summary, raw=raw)

            if status == 'finishedSuccessfully':
                self.handle_finished_successfully_status()
            elif status == 'finishedWithError':
                self.handle_finished_with_error_status()
            elif status == 'undefined':
                self.handle_undefined_status()
        return self.c_plugin_inst.status

    def cancel_exec(self):
        """
        Cancel a plugin instance upload job execution. It connects to the remote service
        to cancel job and schedules remote cleanup.
        """
        self.c_plugin_inst.status = 'cancelled'
        self.c_plugin_inst.save(update_fields=['status'])
        self.schedule_remote_cleanup()

    def delete(self):
        """
        Delete a plugin instance upload job from the remote compute. It connects to the
        remote service to delete the job.
        """
        pfcon_url = self.pfcon_client.url
        job_id = self.str_job_id
        logger.info(f'Deleting upload job {job_id} from pfcon at url '
                    f'-->{pfcon_url}<--')
        try:
            self._delete(JobType.UPLOAD, job_id)
        except PfconRequestException as e:
            logger.error(f'[CODE12,{job_id}]: Error deleting upload job from '
                             f'pfcon at url -->{pfcon_url}<--, detail: {str(e)}')
            self.c_plugin_inst.error_code = 'CODE12'
        else:
            logger.info(f'Successfully deleted upload job {job_id} from pfcon at '
                        f'url -->{pfcon_url}<--')
            if self.c_plugin_inst.error_code == 'CODE12':
                self.c_plugin_inst.error_code = ''

    def handle_finished_successfully_status(self):
        """
        Handle the 'finishedSuccessfully' status returned by the remote compute.
        Delegates to PluginInstanceAppJob to fetch file metadata from pfcon, verify
        files in storage and register them with the DB. The files registration
        must execute only once.
        """
        plg_inst_lock = PluginInstanceLock(plugin_inst=self.c_plugin_inst)
        try:
            plg_inst_lock.save()
        except IntegrityError:
            # another async task has already entered the lock section of the code
            # only update (atomically) if status='started' to avoid concurrency problems
            PluginInstance.objects.filter(
                id=self.c_plugin_inst.id,
                status='uploading').update(status='registeringFiles', 
                                         end_date=timezone.now())
        else:
            # only one concurrent async task should execute this lock section of the code
            self.c_plugin_inst.status = 'registeringFiles'
            self.c_plugin_inst.save(update_fields=['status'])

            job_id = self.str_job_id
            logger.info(f'Successfully finished plugin instance upload job {job_id}')

            pfcon_url = self.pfcon_client.url
            logger.info(f'Sending job status request to pfcon url -->{pfcon_url}<-- for '
                        f'plugin job {job_id}')
            try:
                d_resp = self._get_status(JobType.PLUGIN, job_id)
            except PfconRequestException as e:
                logger.error(f'[CODE02,{job_id}]: Error getting plugin job status at '
                             f'pfcon url -->{pfcon_url}<-- while registering files, '
                             f'detail: {str(e)}')
                
                self.c_plugin_inst.status = 'cancelled'
                self.c_plugin_inst.error_code = 'CODE02'
                self.c_plugin_inst.save(update_fields=['status', 'error_code'])
                self.schedule_remote_cleanup()
            else:
                logger.info(f'Successful job status response from pfcon url '
                            f'-->{pfcon_url}<-- for plugin job {job_id}: '
                            f'{json.dumps(d_resp, indent=4)} while registering files')
                
                from .pluginjobs import PluginInstanceAppJob
                app_job = PluginInstanceAppJob(self.c_plugin_inst)  
                
                if d_resp['compute']['status'] == 'finishedSuccessfully':
                    app_job.register_output_files_on_success()
                elif d_resp['compute']['status'] == 'finishedWithError':
                    app_job.register_output_files_on_error()

    def handle_finished_with_error_status(self):
        """
        Handle the 'finishedWithError' status returned by the remote compute.
        """
        job_id = self.str_job_id

        logger.error(f'[CODE18,{job_id}]: Error while running upload job, remote compute '
                     f'returned finishedWithError status for job {job_id}')
        
        self.c_plugin_inst.status = 'cancelled'
        self.c_plugin_inst.error_code = 'CODE18'
        self.c_plugin_inst.save(update_fields=['status', 'error_code'])
        self.schedule_remote_cleanup()

    def handle_undefined_status(self):
        """
        Handle the 'undefined' status returned by the remote compute.
        """
        self.c_plugin_inst.upload_retry_count += 1

        if self.c_plugin_inst.upload_retry_count > PluginInstance.MAX_UPLOAD_RETRIES:
            job_id = self.str_job_id

            logger.error(f'[CODE18,{job_id}]: Error while running upload job, remote '
                        f'compute returned undefined status for job {job_id} and '
                        f'exceeded max upload retries')
            
            self.c_plugin_inst.status = 'cancelled'
            self.c_plugin_inst.error_code = 'CODE18'
            self.c_plugin_inst.save(update_fields=['status', 'error_code'])
            self.schedule_remote_cleanup()
        else:
            self.c_plugin_inst.save(update_fields=['upload_retry_count'])
            self.run()  # retry
