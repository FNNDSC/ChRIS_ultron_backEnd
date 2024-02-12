"""
Plugin instance app manager module that provides functionality to run and check the
execution status of a plugin instance's app (ChRIS / pfcon interface).

NOTE:

    This module is executed as part of an asynchronous celery worker.
    For instance, to debug 'check_plugin_instance_app_exec_status' method synchronously
    with pudb.set_trace() you need to:

    1. Once CUBE is running, and assuming some plugininstance has been POSTed, start a
    python shell on the manage.py code (note <IMAGE> below is the chris:dev container):

    docker exec -ti <IMAGE> python manage.py shell

    You should now be in a python shell.

    2. To simulate operations on a given plugin with id <id>,
    instantiate the relevant objects (for ex, for id=1):

    from plugininstances.models import PluginInstance
    from plugininstances.services import manager

    plg_inst = PluginInstance.objects.get(id=1)
    plg_inst_manager = manager.PluginInstanceManager(plg_inst)

    3. And finally, call the method:

    plg_inst_manager.check_plugin_instance_app_exec_status()

    Any pudb.set_trace() calls in this method will now be handled by the pudb debugger.

    4. Finally, after each change to this method, reload this module:

    import importlib
    importlib.reload(manager)

    and also re-instantiate the service:

    plg_inst_manager = manager.PluginInstanceManager(plg_inst)
"""

import logging
import os
import re
import io
import time
import json
import zipfile
from typing import List, Optional
from pfconclient import client as pfcon
from pfconclient.exceptions import (PfconRequestException,
                                    PfconRequestInvalidTokenException)

from django.utils import timezone
from django.conf import settings
from django.db.utils import IntegrityError

from core.storage import connect_storage
from core.utils import json_zip2str
from core.models import ChrisInstance, ChrisFolder, ChrisLinkFile
from plugininstances.models import PluginInstance, PluginInstanceLock
from userfiles.models import UserFile

if settings.DEBUG:
    import pdb, pudb, rpudb
    from celery.contrib import rdb


logger = logging.getLogger(__name__)


class PluginInstanceManager(object):

    def __init__(self, plugin_instance):

        self.c_plugin_inst = plugin_instance

        self.l_plugin_inst_param_instances = self.c_plugin_inst.get_parameter_instances()

        self.str_job_id_prefix = ChrisInstance.load().job_id_prefix
        self.str_job_id = self.str_job_id_prefix + str(plugin_instance.id)

        cr = self.c_plugin_inst.compute_resource
        self.pfcon_client = pfcon.Client(cr.compute_url, cr.compute_auth_token)
        self.pfcon_client.pfcon_innetwork = cr.compute_innetwork

        self.plugin_inst_output_files = set() # set of obj names in object storage

        self.storage_manager = connect_storage(settings)
        self.storage_env = settings.STORAGE_ENV

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

    def run_plugin_instance_app(self):
        """
        Run the plugin instance's app via a call to a remote pfcon service.
        """
        if self.c_plugin_inst.status == 'cancelled':
            return

        plugin = self.c_plugin_inst.plugin
        plugin_type = plugin.meta.type
        inputdirs = []

        d_unextpath_params, d_path_params = self.get_plugin_instance_path_parameters()
        for path_param_value in [param_value for param_value in d_path_params.values()]:
            # the value of each parameter of type 'path' is a string
            # representing a comma-separated list of paths in obj storage
            inputdirs = inputdirs + path_param_value.split(',')

        try:
            if plugin_type == 'ds':
                inputdirs.append(self.get_previous_output_path())
            elif not inputdirs:
                inputdirs.append(self.manage_plugin_instance_app_empty_inputdir())
        except Exception:
            self.c_plugin_inst.status = 'cancelled'  # giving up
            self.save_plugin_instance_final_status()
            return

        # create job description dictionary
        job_descriptors = {
            'entrypoint': self._assemble_exec(plugin.selfpath, plugin.selfexec, plugin.execshell),
            'args': self.get_plugin_instance_app_cmd_args(),
            'args_path_flags': [*d_unextpath_params.keys(), *d_path_params.keys()],
            'auid': self.c_plugin_inst.owner.username,
            'number_of_workers': self.c_plugin_inst.number_of_workers,
            'cpu_limit': self.c_plugin_inst.cpu_limit,
            'memory_limit': self.c_plugin_inst.memory_limit,
            'gpu_limit': self.c_plugin_inst.gpu_limit,
            'image': plugin.dock_image,
            'type': plugin_type,
            'env': self._compute_env_vars()
        }

        job_zip_file_content = None
        job_timeout = 1000

        if self.pfcon_client.pfcon_innetwork:
            job_descriptors['input_dirs'] = inputdirs

            if self.storage_env == 'filesystem':
                job_timeout = 200
                output_dir = self.c_plugin_inst.get_output_path()
                # remote pfcon requires both the input and output dirs to exist
                os.makedirs(os.path.join(settings.MEDIA_ROOT, output_dir), exist_ok=True)
                job_descriptors['output_dir'] = output_dir
        else:
            # create zip file to transmit
            try:
                job_zip_file = self.create_zip_file(inputdirs)
            except Exception:
                self.c_plugin_inst.status = 'cancelled'  # giving up
                self.save_plugin_instance_final_status()
                return
            job_zip_file_content = job_zip_file.getvalue()
            job_timeout = 9000

        job_id = self.str_job_id
        pfcon_url = self.pfcon_client.url
        logger.info(f'Submitting job {job_id} to pfcon url -->{pfcon_url}<--, '
                    f'description: {json.dumps(job_descriptors, indent=4)}')
        try:
            d_resp = self._submit_job(job_id, job_descriptors, job_zip_file_content,
                                      job_timeout)
        except PfconRequestException as e:
            logger.error(f'[CODE01,{job_id}]: Error submitting job to pfcon url '
                         f'-->{pfcon_url}<--, detail: {str(e)}')
            self.c_plugin_inst.error_code = 'CODE01'
            self.c_plugin_inst.status = 'cancelled'  # giving up
            self.save_plugin_instance_final_status()
        else:
            logger.info(f'Successfully submitted job {job_id} to pfcon url '
                        f'-->{pfcon_url}<--, response: {json.dumps(d_resp, indent=4)}')
            # update the job status and summary
            self.c_plugin_inst.status = 'started'
            self.c_plugin_inst.summary = self.get_job_status_summary()  # initial status
            self.c_plugin_inst.raw = json_zip2str(d_resp)
            self.c_plugin_inst.save()

            # https://github.com/FNNDSC/ChRIS_ultron_backEnd/issues/408
            now = timezone.now()
            self.c_plugin_inst.start_date = now
            self.c_plugin_inst.end_date = now

    @staticmethod
    def _assemble_exec(selfpath: Optional[str], selfexec: str, execshell: Optional[str]) -> List[str]:
        entrypoint_path = selfexec
        if selfpath:
            entrypoint_path = os.path.join(selfpath, selfexec)
        if not execshell:
            return [entrypoint_path]
        return [execshell, entrypoint_path]

    def _compute_env_vars(self):
        """
        Helper method to compute a list of environment variables to be injected into
        remote plugin's container.
        """
        job_id = self.str_job_id
        plugin_inst = self.c_plugin_inst
        plugin = plugin_inst.plugin
        plugin_type = plugin.meta.type
        username = plugin_inst.owner.username
        email = plugin_inst.owner.email

        env = [f'CHRIS_JID={job_id}', f'CHRIS_PLG_INST_ID={plugin_inst.id}',
               f'CHRIS_USER_USERNAME={username}', f'CHRIS_USER_EMAIL={email}']

        if plugin_type != 'fs':
            prev_id = plugin_inst.previous.id
            env.append(f'CHRIS_PREV_PLG_INST_ID={prev_id}')
            env.append(f'CHRIS_PREV_JID={self.str_job_id_prefix + str(prev_id)}')

        if plugin_inst.workflow:
            workflow_instances_info = ''
            for inst in plugin_inst.workflow.plugin_instances.all():
                workflow_instances_info += f'{inst.title}:{inst.id},'
            env.append(f'CHRIS_WORKFLOW_ID={plugin_inst.workflow.id}')
            env.append(f'CHRIS_PIPELINE_ID={plugin_inst.workflow.pipeline.id}')
            env.append(f'CHRIS_WORKFLOW_PLG_INSTANCES={workflow_instances_info[:-1]}')
        return env

    def _submit_job(self, job_id, job_descriptors, dfile, timeout=1000):
        """
        Submit job to a remote pfcon service.
        """
        try:
            d_resp = self.pfcon_client.submit_job(job_id, job_descriptors, dfile, timeout)
        except PfconRequestInvalidTokenException:
            logger.info(f'Auth token has expired while submitting job {job_id} to pfcon '
                        f'url -->{self.pfcon_client.url}<--')
            self._refresh_compute_resource_auth_token()
            d_resp = self.pfcon_client.submit_job(job_id, job_descriptors, dfile, timeout)
        except PfconRequestException:
            # FIXME HACK
            # Under some conditions, the requests library will produce a "Connection Aborted"
            # error instead of a 401 response. This happens when pfcon responds eagerly
            # to an invalid token and closes the connection while CUBE is trying to transmit
            # a large zip file.
            # The temporary workaround is to catch a wider range of Exceptions here.
            # Ideally we only want to try again in the event that we know the token is
            # invalid, PfconRequestInvalidTokenException, however PfconRequestInvalidTokenException
            # is not correctly raised in all the situations where it should be.
            #
            logger.exception(f'Error while submitting job {job_id} to pfcon url '
                             f'-->{self.pfcon_client.url}<--, auth token might have '
                             f'expired, will try refreshing token and resubmitting job')
            self._refresh_compute_resource_auth_token()
            d_resp = self.pfcon_client.submit_job(job_id, job_descriptors, dfile, timeout)
        return d_resp

    def check_plugin_instance_app_exec_status(self):
        """
        Check a plugin instance's app execution status. If the associated job's
        execution time exceeds the maximum set for the remote compute environment then
        the job is cancelled. Otherwise the job's execution status is fetched from the
        remote and if finished (with or without errors) then the job's zip file is
        downloaded and unpacked and the output files registered with the DB. Finally a
        delete request is made to remove the job from the remote environment.
        """
        if self.c_plugin_inst.status == 'started':
            job_id = self.str_job_id

            max_job_exec_sec = self.c_plugin_inst.compute_resource.max_job_exec_seconds
            if max_job_exec_sec >= 0:
                delta_exec_time = timezone.now() - self.c_plugin_inst.start_date
                delta_seconds = delta_exec_time.total_seconds()
                if delta_seconds > max_job_exec_sec:
                    logger.error(f'[CODE13,{job_id}]: Error, job exceeded maximum '
                                 f'execution time ({max_job_exec_sec} seconds)')
                    self.c_plugin_inst.error_code = 'CODE13'
                    self.cancel_plugin_instance_app_exec()
                    return self.c_plugin_inst.status

            pfcon_url = self.pfcon_client.url
            logger.info(f'Sending job status request to pfcon url -->{pfcon_url}<-- for '
                        f'job {job_id}')
            try:
                d_resp = self._get_job_status(job_id)
            except PfconRequestException as e:
                logger.error(f'[CODE02,{job_id}]: Error getting job status at pfcon '
                             f'url -->{pfcon_url}<--, detail: {str(e)}')
                return self.c_plugin_inst.status  # return, CUBE will retry later

            logger.info(f'Successful job status response from pfcon url -->{pfcon_url}<--'
                        f' for job {job_id}: {json.dumps(d_resp, indent=4)}')
            status = d_resp['compute']['status']
            logger.info(f'Current job {job_id} remote status = {status}')
            logger.info(f'Current job {job_id} DB status = {self.c_plugin_inst.status}')

            summary = self.get_job_status_summary(d_resp)
            self.c_plugin_inst.summary = summary
            raw = json_zip2str(d_resp)
            self.c_plugin_inst.raw = raw
            # only update (atomically) if status='started' to avoid concurrency problems
            PluginInstance.objects.filter(
                id=self.c_plugin_inst.id,
                status='started').update(summary=summary, raw=raw)

            if status == 'finishedSuccessfully':
                self._handle_finished_successfully_status()
            elif status == 'finishedWithError':
                self._handle_finished_with_error_status()
            elif status == 'undefined':
                self._handle_undefined_status()
        return self.c_plugin_inst.status

    def _get_job_status(self, job_id, timeout=200):
        """
        Get job status from a remote pfcon service.
        """
        try:
            d_resp = self.pfcon_client.get_job_status(job_id, timeout)
        except PfconRequestInvalidTokenException:
            logger.info(f'Auth token has expired while getting status for job {job_id} '
                        f'from pfcon url -->{self.pfcon_client.url}<--')
            self._refresh_compute_resource_auth_token()
            d_resp = self.pfcon_client.get_job_status(job_id, timeout)
        return d_resp

    def cancel_plugin_instance_app_exec(self):
        """
        Cancel a plugin instance's app execution. It connects to the remote service
        to cancel job.
        """
        self.c_plugin_inst.status = 'cancelled'
        self.delete_plugin_instance_job_from_remote()
        self.save_plugin_instance_final_status()

    def delete_plugin_instance_job_from_remote(self):
        """
        Delete a plugin instance's app job from the remote compute. It connects to the
        remote service to delete job.
        """
        pfcon_url = self.pfcon_client.url
        job_id = self.str_job_id
        logger.info(f'Deleting job {job_id} from pfcon at url '
                    f'-->{pfcon_url}<--')
        try:
            self._delete_job(job_id)
        except PfconRequestException as e:
            logger.error(f'[CODE12,{job_id}]: Error deleting job from '
                         f'pfcon at url -->{pfcon_url}<--, detail: {str(e)}')
        else:
            logger.info(f'Successfully deleted job {job_id} from pfcon at '
                        f'url -->{pfcon_url}<--')

    def _delete_job(self, job_id, timeout=500):
        """
        Delete a job from a remote pfcon service.
        """
        try:
            self.pfcon_client.delete_job(job_id, timeout)
        except PfconRequestInvalidTokenException:
            logger.info(f'Auth token has expired while requesting to delete job {job_id} '
                        f'from pfcon url -->{self.pfcon_client.url}<--')
            self._refresh_compute_resource_auth_token()
            self.pfcon_client.delete_job(job_id, timeout)

    def get_previous_output_path(self):
        """
        Get the previous plugin instance output directory. Make sure to deal with
        the eventual consistency.
        """
        job_id = self.str_job_id
        previous = self.c_plugin_inst.previous
        output_path = previous.get_output_path()
        output_folders = previous.output_folder.get_descendants()
        fnames = []
        for folder in output_folders:
            fnames.extend([f.fname.name for f in folder.user_files.all()])
        for i in range(20):  # loop to deal with eventual consistency
            try:
                l_ls = self.storage_manager.ls(output_path)
            except Exception as e:
                logger.error(f'[CODE06,{job_id}]: Error while listing storage files '
                             f'in {output_path}, detail: {str(e)}')
            else:
                if all(obj in l_ls for obj in fnames):
                    return output_path
            time.sleep(3)
        logger.error(f'[CODE11,{job_id}]: Error while listing storage files in '
                     f'{output_path}, detail: Presumable eventual consistency problem')
        self.c_plugin_inst.error_code = 'CODE11'
        raise NameError('Presumable eventual consistency problem.')

    def get_plugin_instance_app_cmd_args(self) -> List[str]:
        # append flags to save input meta data (passed options) and
        # output meta data (output description)
        app_args = ['--saveinputmeta', '--saveoutputmeta']
        # append the parameters to app's argument list
        for param_inst in self.l_plugin_inst_param_instances:
            param = param_inst.plugin_param
            value = param_inst.value
            if param.action == 'store':
                app_args.append(param.flag)
                app_args.append(str(value))  # convert all argument values to string
            elif param.action == 'store_true' and value:
                app_args.append(param.flag)
            elif param.action == 'store_false' and not value:
                app_args.append(param.flag)
        return app_args

    def get_plugin_instance_path_parameters(self):
        """
        Get the unextpath and path parameters dictionaries in a tuple. The keys and
        values in these dictionaries are parameters' flag and value respectively.
        """
        path_parameters_dict = {}
        unextpath_parameters_dict = {}
        for param_inst in self.l_plugin_inst_param_instances:
            param = param_inst.plugin_param
            value = param_inst.value
            if param.type == 'unextpath':
                unextpath_parameters_dict[param.flag] = value
            if param.type == 'path':
                path_parameters_dict[param.flag] = value
        return unextpath_parameters_dict, path_parameters_dict

    def get_ts_plugin_instance_input_objs(self):
        """
        Get a tuple whose first element is a dictionary with keys that are the ids of
        each input plugin instance to this 'ts' plugin instance. The values of
        this dictionary are also dictionaries containing the output dir of the plugin
        instances and the list of all the objects under the output dir that match a
        regular expression. The second element of the tuple indicates the value of the
        'groupByInstance' flag for this 'ts' plugin instance.
        """
        job_id = self.str_job_id
        # extract the 'ts' plugin's special parameters from the DB
        plg_inst_ids = regexs = []
        group_by_instance = False

        if self.c_plugin_inst.plugin.meta.type == 'ts':
            for param_inst in self.l_plugin_inst_param_instances:
                if param_inst.plugin_param.name == 'plugininstances':
                    # string param that represents a comma-separated list of ids
                    plg_inst_ids = param_inst.value.split(',') if param_inst.value else []
                elif param_inst.plugin_param.name == 'filter':
                    # string param that represents a comma-separated list of regular expr
                    regexs = param_inst.value.split(',') if param_inst.value else []
                elif param_inst.plugin_param.name == 'groupByInstance':
                    group_by_instance = param_inst.value

        d_objs = {}
        for i, inst_id in enumerate(plg_inst_ids):
            try:
                plg_inst = PluginInstance.objects.get(pk=int(inst_id))
            except PluginInstance.DoesNotExist:
                logger.error(f"[CODE05,{job_id}]: Couldn't find any plugin instance with "
                             f"id {inst_id} while processing input instances to 'ts' "
                             f"plugin instance with id {self.c_plugin_inst.id}")
                self.c_plugin_inst.error_code = 'CODE05'
                raise

            output_path = plg_inst.get_output_path()
            all_obj_paths = set()
            visited_paths = set()
            self.find_all_storage_object_paths(output_path, all_obj_paths, visited_paths)

            if (i < len(regexs)) and regexs[i]:
                r = re.compile(regexs[i])
                d_objs[plg_inst.id] = {'output_path': output_path,
                                       'objs': [obj for obj in all_obj_paths if
                                                r.search(obj)]}
            else:
                d_objs[plg_inst.id] = {'output_path': output_path,
                                       'objs': list(all_obj_paths)}
        return d_objs, group_by_instance

    def manage_plugin_instance_app_empty_inputdir(self):
        """
        This method is responsible for managing the 'inputdir' in the case of
        FS and TS plugins. FS and TS plugins do not have an inputdir spec, since this
        is only a requirement for DS plugins. Nonetheless, the remote services do
        require some non-zero inputdir spec in order to operate correctly.

        The hack here is to store data somewhere in storage and accessing it as a
        "pseudo" inputdir for FS and TS plugins. We create a "dummy" inputdir with a
        small dummy text file in storage. This is then transmitted as an 'inputdir'
        to the compute environment and can be completely ignored by the plugin.
        """
        job_id = self.str_job_id
        data_dir = os.path.join(os.path.expanduser("~"), 'data')
        str_inputdir = os.path.join(data_dir, 'squashEmptyDir').lstrip('/')
        str_squashFile = os.path.join(str_inputdir, 'squashEmptyDir.txt')
        str_squashMsg = 'Empty input dir.'
        try:
            if not self.storage_manager.obj_exists(str_squashFile):
                with io.StringIO(str_squashMsg) as f:
                    self.storage_manager.upload_obj(str_squashFile, f.read(),
                                                    content_type='text/plain')
        except Exception as e:
            logger.error(f'[CODE07,{job_id}]: Error while uploading file '
                         f'{str_squashFile} to storage, detail: {str(e)}')
            self.c_plugin_inst.error_code = 'CODE07'
            raise
        return str_inputdir

    def find_all_storage_object_paths(self, storage_path, obj_paths, visited_paths):
        """
        Find all object storage paths from the passed storage path (prefix) by
        recursively following ChRIS links. The resulting set of object paths is given
        by the obj_paths set argument.
        """
        if not storage_path.startswith(tuple(visited_paths)):  # avoid infinite loops
            visited_paths.add(storage_path)
            job_id = self.str_job_id
            output_dir = self.c_plugin_inst.get_output_path()

            try:
                l_ls = self.storage_manager.ls(storage_path)
            except Exception as e:
                logger.error(f'[CODE06,{job_id}]: Error while listing storage files '
                             f'in {storage_path}, detail: {str(e)}')
                self.c_plugin_inst.error_code = 'CODE06'
                raise

            for obj_path in l_ls:
                if obj_path.endswith('.chrislink'):
                    try:
                        linked_path = self.storage_manager.download_obj(obj_path).decode()
                    except Exception as e:
                        logger.error(f'[CODE08,{job_id}]: Error while downloading file '
                                     f'{obj_path} from storage, detail: {str(e)}')
                        self.c_plugin_inst.error_code = 'CODE08'
                        raise

                    if f'{output_dir}/'.startswith(linked_path.rstrip('/') + '/'):
                        # link files are not allowed to point to the output dir or any
                        # of its ancestors
                        logger.error(
                            f'[CODE17,{job_id}]: Found invalid input path {linked_path} '
                            f'pointing to an ancestor of the output dir: '
                            f'{output_dir}')
                        self.c_plugin_inst.error_code = 'CODE17'
                        raise ValueError(f'Invalid input path: {linked_path}')

                    self.find_all_storage_object_paths(linked_path, obj_paths,
                                                       visited_paths)  # recursive call
                obj_paths.add(obj_path)

    def create_zip_file(self, storage_paths):
        """
        Create job zip file ready for transmission to the remote from a list of storage
        paths (prefixes).
        """
        job_id = self.str_job_id
        memory_zip_file = io.BytesIO()
        all_obj_paths = set()

        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_data_zip:
            for storage_path in storage_paths:
                obj_paths = set()
                visited_paths = set()

                self.find_all_storage_object_paths(storage_path, obj_paths,
                                                   visited_paths)
                for obj_path in obj_paths:
                    if obj_path not in all_obj_paths:  # add a file to the zip only once
                        try:
                            contents = self.storage_manager.download_obj(obj_path)
                        except Exception as e:
                            logger.error(f'[CODE08,{job_id}]: Error while downloading file '
                                         f'{obj_path} from storage, detail: {str(e)}')
                            self.c_plugin_inst.error_code = 'CODE08'
                            raise
                        zip_path = obj_path.replace(storage_path, '', 1).lstrip('/')
                        job_data_zip.writestr(zip_path, contents)
                        all_obj_paths.add(obj_path)

        memory_zip_file.seek(0)
        return memory_zip_file

    def unpack_zip_file(self, zip_file_content):
        """
        Unpack job zip file from the remote into storage.
        """
        job_id = self.str_job_id
        try:
            memory_zip_file = io.BytesIO(zip_file_content)
            with zipfile.ZipFile(memory_zip_file, 'r', zipfile.ZIP_DEFLATED) as job_zip:
                filenames = job_zip.namelist()
                logger.info(f'{len(filenames)} files to decompress for job {job_id}')
                output_path = self.c_plugin_inst.get_output_path() + '/'
                for fname in filenames:
                    content = job_zip.read(fname)
                    storage_fname = output_path + fname.lstrip('/')
                    try:
                        self.storage_manager.upload_obj(storage_fname, content)
                    except Exception as e:
                        logger.error(f'[CODE07,{job_id}]: Error while uploading file '
                                     f'{storage_fname} to storage, detail: {str(e)}')
                        self.c_plugin_inst.error_code = 'CODE07'
                        raise ValueError(str(e))
                    self.plugin_inst_output_files.add(storage_fname)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f'[CODE04,{job_id}]: Received bad zip file from remote, '
                         f'detail: {str(e)}')
            self.c_plugin_inst.error_code = 'CODE04'
            raise

    def check_files_from_json_exist(self, json_file_content):
        """
        Check whether all files listed in the job json file from the remote indeed
        exist in storage.
        """
        job_id = self.str_job_id
        plg_inst_output_path = self.c_plugin_inst.get_output_path()
        job_output_path = json_file_content['job_output_path']

        if  job_output_path != plg_inst_output_path:
            err_msg = f'Received {job_output_path} != {plg_inst_output_path} output path'
            logger.error(f'[CODE16,{job_id}]: Inconsistency between received '
                         f'JSON file and storage, detail: {err_msg}')
            self.c_plugin_inst.error_code = 'CODE16'
            raise ValueError(err_msg)

        files_from_json = set([os.path.join(job_output_path, p) for p in
                               json_file_content['rel_file_paths']])

        for i in range(60):  # check for 60 seconds at 1-sec intervals
            try:
                files_in_storage = set(self.storage_manager.ls(job_output_path))
            except Exception as e:
                logger.error(f'[CODE15,{job_id}]: Error while listing storage files '
                             f'in {job_output_path}, detail: {str(e)}')
                self.c_plugin_inst.error_code = 'CODE15'
                raise

            if not files_from_json.issubset(files_in_storage):
                if i == 59:
                    nmissing = len(files_from_json.difference(files_in_storage))
                    err_msg = f'Missing {nmissing} files in storage'
                    logger.error(f'[CODE14,{job_id}]: Inconsistency between received '
                                 f'JSON file and storage, detail: {err_msg}')
                    self.c_plugin_inst.error_code = 'CODE14'
                    raise ValueError(err_msg)
                time.sleep(1)
        self.plugin_inst_output_files = files_from_json

    def save_plugin_instance_final_status(self):
        """
        Save to the DB and log the final status of the plugin instance.
        """
        job_id = self.str_job_id
        logger.info(f"Saving job {job_id} DB status as '{self.c_plugin_inst.status}'")
        self.c_plugin_inst.end_date = timezone.now()
        logger.info(f"Saving job {job_id} DB end_date as '{self.c_plugin_inst.end_date}'")
        self.c_plugin_inst.save()

    def _handle_app_unextpath_parameters(self, unextpath_parameters_dict):
        """
        Internal method to handle parameters of type 'unextpath' passed to the
        plugin instance app.

        NOTE:
        Full storage path names are given to the link file names, allowing
        for each copy argument to have its own link file in the output directory.

        NB: This preservation could exhaust DB string lengths!
        """
        job_id: str = self.str_job_id
        output_dir: str = self.c_plugin_inst.get_output_path()
        owner = self.c_plugin_inst.owner

        (link_parent_folder, _) = ChrisFolder.objects.get_or_create(
            path=output_dir, owner=owner)

        for param_flag in unextpath_parameters_dict:
            # each parameter value is a string of one or more paths separated by comma
            path_list = unextpath_parameters_dict[param_flag].split(',')

            for path in path_list:
                if f'{output_dir}/'.startswith(path.rstrip('/') + '/'):
                    # paths are not allowed to point to the output dir or any
                    # of its ancestors
                    logger.error(f'[CODE17,{job_id}]: Found invalid input path {path} '
                                 f'pointing to an ancestor of the output dir: '
                                 f'{output_dir}')
                    self.c_plugin_inst.error_code = 'CODE17'
                    raise ValueError(f'Invalid input path: {path}')

            for path in path_list:
                str_source_trace_dir = path.rstrip('/').replace('/', '_')
                try:
                    ChrisFolder.objects.get(path=path)
                except ChrisFolder.DoesNotExist:
                    try:
                        if self.storage_manager.obj_exists(path):  # path is a file
                            link_file = ChrisLinkFile(path=path, owner=owner,
                                                      parent_folder=link_parent_folder)
                            link_file.save(name=str_source_trace_dir)
                            self.plugin_inst_output_files.add(link_file.fname.name)
                    except Exception as e:
                        logger.error(f'[CODE09,{job_id}]: Error while creating link file '
                                     f'to {path} from {output_dir} in storage, '
                                     f'detail: {str(e)}')
                        self.c_plugin_inst.error_code = 'CODE09'
                        raise
                else:  # path is a folder
                    link_file = ChrisLinkFile(path=path, owner=owner,
                                              parent_folder=link_parent_folder)
                    link_file.save(name=str_source_trace_dir)
                    self.plugin_inst_output_files.add(link_file.fname.name)

    def _handle_app_unextpath_parameters_innetwork_filesystem(self, unextpath_parameters_dict):
        """
        Internal method to handle parameters of type 'unextpath' passed to the
        plugin instance app.

        NOTE:
        Full storage path names are now preserved in the copy process, allowing
        for each copy argument to be preserved in its own directory tree in the
        destination.

        NB: This preservation could exhaust DB string lengths!
        """
        job_id                  : str = self.str_job_id
        outputdir               : str = self.c_plugin_inst.get_output_path()

        for param_flag in unextpath_parameters_dict:
            # each parameter value is a string of one or more paths separated by comma
            path_list = unextpath_parameters_dict[param_flag].split(',')

            for path in path_list:
                try:
                    obj_list = self.storage_manager.ls(path)
                except Exception as e:
                    logger.error(f'[CODE06,{job_id}]: Error while listing storage files '
                                 f'in {path}, detail: {str(e)}')
                    self.c_plugin_inst.error_code = 'CODE06'
                    raise

                str_source_trace_dir = path.rstrip('/').replace('/', '_')

                for obj in obj_list:
                    # Uncomment the following to fire up a trace event, accessible via
                    #                   telnet localhot 6900
                    # Note, you might need to change the term_size on an ad-hoc manner
                    # set_trace(host = "0.0.0.0", port = 6900, term_size = (223, 60))
                    obj_output_path = outputdir + '/' + str_source_trace_dir + '/' + obj.replace(
                        path, '', 1).lstrip('/')

                    try:
                        if not self.storage_manager.obj_exists(obj_output_path):
                            self.storage_manager.copy_obj(obj, obj_output_path)
                    except Exception as e:
                        logger.error(f'[CODE09,{job_id}]: Error while copying file '
                                     f'from {obj} to {obj_output_path} in storage, '
                                     f'detail: {str(e)}')
                        self.c_plugin_inst.error_code = 'CODE09'
                        raise
                    self.plugin_inst_output_files.add(obj_output_path)

    def _handle_app_ts_unextracted_input_objs(self, d_ts_input_objs, group_by_instance):
        """
        Internal method to handle a 'ts' plugin's input instances' filtered objects
        (which are not extracted from object storage).
        """
        job_id = self.str_job_id
        outputdir = self.c_plugin_inst.get_output_path()

        for plg_inst_id in d_ts_input_objs:
            plg_inst_output_path = d_ts_input_objs[plg_inst_id]['output_path']
            obj_list = d_ts_input_objs[plg_inst_id]['objs']
            plg_inst_outputdir = outputdir

            if group_by_instance:
                plg_inst_outputdir = os.path.join(outputdir, str(plg_inst_id))

            for obj in obj_list:
                obj_output_path = os.path.join(plg_inst_outputdir, obj.replace(
                    plg_inst_output_path, '', 1).lstrip('/'))
                try:
                    if not self.storage_manager.obj_exists(obj_output_path):
                        self.storage_manager.copy_obj(obj, obj_output_path)
                except Exception as e:
                    logger.error(f'[CODE09,{job_id}]: Error while copying file '
                                 f'from {obj} to {obj_output_path} in storage, '
                                 f'detail: {str(e)}')
                    self.c_plugin_inst.error_code = 'CODE09'
                    raise
                self.plugin_inst_output_files.add(obj_output_path)

    def _handle_finished_successfully_status(self):
        """
        Internal method to handle the 'finishedSuccessfully' status returned by the
        remote compute.
        """
        plg_inst_lock = PluginInstanceLock(plugin_inst=self.c_plugin_inst)
        try:
            plg_inst_lock.save()
        except IntegrityError:
            pass  # another async task has already entered here
        else:
            # only one concurrent async task should get here
            pfcon_url = self.pfcon_client.url
            job_id = self.str_job_id
            logger.info(f'Sending job data file request to pfcon url -->{pfcon_url}<-- '
                        f'for job {job_id}')
            try:
                if self.pfcon_client.pfcon_innetwork:
                    job_output_path = self.c_plugin_inst.get_output_path()
                    job_file_content = self._get_job_json_data(job_id, job_output_path)
                else:
                    job_file_content = self._get_job_zip_data(job_id)
            except PfconRequestException as e:
                logger.error(f'[CODE03,{job_id}]: Error fetching data file from pfcon '
                             f'url -->{pfcon_url}<--, detail: {str(e)}')
                self.c_plugin_inst.error_code = 'CODE03'
                self.c_plugin_inst.status = 'cancelled'  # giving up
            else:
                # data successfully downloaded so update summary and instance status
                d_jobStatusSummary = json.loads(self.c_plugin_inst.summary)
                d_jobStatusSummary['pullPath']['status'] = True
                self.c_plugin_inst.summary = json.dumps(d_jobStatusSummary)
                self.c_plugin_inst.status = 'registeringFiles'
                self.c_plugin_inst.save()  # inform FE about status change

                try:
                    if self.pfcon_client.pfcon_innetwork:
                        logger.info('Checking that all remote output files for job %s '
                                    'exist in file storage', job_id)
                        self.check_files_from_json_exist(job_file_content)
                    else:
                        logger.info('Uploading remote output files for job %s to file '
                                    'storage', job_id)
                        self.unpack_zip_file(job_file_content)

                    logger.info('Copying local output files for job %s in file storage',
                                job_id)
                    # upload(copy) files from unextracted path parameters
                    d_unextpath_params, _ = self.get_plugin_instance_path_parameters()
                    if d_unextpath_params:
                        if (self.pfcon_client.pfcon_innetwork and self.storage_env ==
                                'filesystem'):
                            self._handle_app_unextpath_parameters_innetwork_filesystem(
                                d_unextpath_params)
                        else:
                            self._handle_app_unextpath_parameters(d_unextpath_params)

                    # upload(copy) files from filtered input instance paths ('ts' plugins)
                    if self.c_plugin_inst.plugin.meta.type == 'ts':
                        d_ts_input_objs, tf = self.get_ts_plugin_instance_input_objs()
                        self._handle_app_ts_unextracted_input_objs(d_ts_input_objs, tf)

                    self._register_output_files()  # register output files in the DB
                except Exception:
                    self.c_plugin_inst.status = 'cancelled'  # giving up
                else:
                    self.c_plugin_inst.status = 'finishedSuccessfully'
            self.delete_plugin_instance_job_from_remote()
            self.save_plugin_instance_final_status()

    def _get_job_json_data(self, job_id, job_output_path, timeout=1000):
        """
        Get job json data from a remote in-network pfcon service.
        """
        try:
            json_content = self.pfcon_client.get_job_json_data(job_id, job_output_path,
                                                              timeout)
        except PfconRequestInvalidTokenException:
            logger.info(f'Auth token has expired while getting json data for job'
                        f' {job_id} from pfcon url -->{self.pfcon_client.url}<--')
            self._refresh_compute_resource_auth_token()
            json_content = self.pfcon_client.get_job_json_data(job_id, job_output_path,
                                                               timeout)
        return json_content

    def _get_job_zip_data(self, job_id, timeout=9000):
        """
        Get job zip data from a remote pfcon service.
        """
        try:
            zip_content = self.pfcon_client.get_job_zip_data(job_id, timeout)
        except PfconRequestInvalidTokenException:
            logger.info(f'Auth token has expired while getting zip data for job {job_id} '
                        f'from pfcon url -->{self.pfcon_client.url}<--')
            self._refresh_compute_resource_auth_token()
            zip_content = self.pfcon_client.get_job_zip_data(job_id, timeout)
        return zip_content

    def _handle_finished_with_error_status(self):
        """
        Internal method to handle the 'finishedWithError' status returned by the
        remote compute.
        """
        plg_inst_lock = PluginInstanceLock(plugin_inst=self.c_plugin_inst)
        try:
            plg_inst_lock.save()
        except IntegrityError:
            pass  # another async task has already entered here
        else:
            # only one concurrent async task should get here
            pfcon_url = self.pfcon_client.url
            job_id = self.str_job_id
            logger.info(f'Sending job data file request to pfcon url -->{pfcon_url}<-- '
                        f'for job {job_id}')
            try:
                if self.pfcon_client.pfcon_innetwork:
                    job_output_path = self.c_plugin_inst.get_output_path()
                    job_file_content = self._get_job_json_data(job_id, job_output_path)
                else:
                    job_file_content = self._get_job_zip_data(job_id)
            except PfconRequestException as e:
                logger.error(f'[CODE03,{job_id}]: Error fetching data file from pfcon '
                             f'url -->{pfcon_url}<--, detail: {str(e)}')
                self.c_plugin_inst.error_code = 'CODE03'
                self.c_plugin_inst.status = 'cancelled'  # giving up
            else:
                # data successfully downloaded so update summary and instance status
                d_jobStatusSummary = json.loads(self.c_plugin_inst.summary)
                d_jobStatusSummary['pullPath']['status'] = True
                self.c_plugin_inst.summary = json.dumps(d_jobStatusSummary)
                self.c_plugin_inst.status = 'registeringFiles'
                self.c_plugin_inst.save()  # inform FE about status change

                try:
                    if self.pfcon_client.pfcon_innetwork:
                        logger.info('Checking that all remote output files for job %s '
                                    'exist in file storage', job_id)
                        self.check_files_from_json_exist(job_file_content)
                    else:
                        logger.info('Uploading remote output files for job %s to file '
                                    'storage', job_id)
                        self.unpack_zip_file(job_file_content)

                    self._register_output_files() # register output files in the DB
                except Exception:
                    pass  # giving up
            self.c_plugin_inst.status = 'finishedWithError'
            self.delete_plugin_instance_job_from_remote()
            self.save_plugin_instance_final_status()

    def _handle_undefined_status(self):
        """
        Internal method to handle the 'undefined' status returned by the
        remote compute.
        """
        job_id = self.str_job_id
        logger.error(f'[CODE10,{job_id}]: Got undefined status from remote')
        self.c_plugin_inst.error_code = 'CODE10'
        self.cancel_plugin_instance_app_exec()

    def _register_output_files(self):
        """
        Internal method to register output files generated for the plugin instance with
        the DB.
        """
        job_id = self.str_job_id
        logger.info('Registering output files with job %s', job_id)

        owner = self.c_plugin_inst.owner
        files = []
        folders = {}

        for obj_name in self.plugin_inst_output_files:
            logger.info(f'Registering file -->{obj_name}<-- for job {job_id}')

            folder_path = os.path.dirname(obj_name)
            parent_folder = folders.get(folder_path)
            if parent_folder is None:
                (parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                       owner=owner)
                folders[folder_path] = parent_folder

            plg_inst_file = UserFile(owner=owner, parent_folder=parent_folder)
            plg_inst_file.fname.name = obj_name
            files.append(plg_inst_file)

        db_files = UserFile.objects.bulk_create(files)

        total_size = 0
        for plg_inst_file in db_files:
            total_size += plg_inst_file.fname.size
        self.c_plugin_inst.size += total_size

    @staticmethod
    def get_job_status_summary(d_response=None):
        """
        Get a job status summary JSON string from pfcon response.
        """
        # Still WIP about what is best summary...

        d_jobStatusSummary = {
            'pushPath': {
                'status': True
            },
            'pullPath': {
                'status': False
            },
            'compute': {
                'submit': {
                    'status': True
                },
                'return': {
                    'status': False,
                    'job_status': '',
                    'job_logs': ''
                }
            },
        }
        if d_response is not None:
            d_c = d_response['compute']
            if d_c['status'] in ('undefined', 'finishedSuccessfully',
                                 'finishedWithError'):
                d_jobStatusSummary['compute']['return']['status'] = True
            d_jobStatusSummary['compute']['return']['job_status'] = d_c['status']
            logs = d_jobStatusSummary['compute']['return']['job_logs'] = d_c['logs']

            # truncate logs, assuming worst case where every character needs to be escaped
            if len(logs) > 1800:
                d_jobStatusSummary['compute']['return']['job_logs'] = logs[-1800:]
        # PostgreSQL allows UTF-8, supports emojis, chinese, etc.
        return json.dumps(d_jobStatusSummary, ensure_ascii=False)
