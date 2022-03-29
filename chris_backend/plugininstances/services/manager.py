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
from pfconclient import client as pfcon
from pfconclient.exceptions import (PfconRequestException,
                                    PfconRequestInvalidTokenException)

from django.utils import timezone
from django.conf import settings
from django.db.utils import IntegrityError

from core.swiftmanager import SwiftManager, ClientException
from core.utils import json_zip2str
from core.models import ChrisInstance
from plugininstances.models import PluginInstance, PluginInstanceFile, PluginInstanceLock

if settings.DEBUG:
    import pdb, pudb, rpudb
    from celery.contrib import rdb
    from pudb.remote    import set_trace


logger = logging.getLogger(__name__)


class PluginInstanceManager(object):

    def __init__(self, plugin_instance):

        self.c_plugin_inst = plugin_instance

        self.l_plugin_inst_param_instances = self.c_plugin_inst.get_parameter_instances()

        self.str_job_id = ChrisInstance.load().job_id_prefix + str(plugin_instance.id)

        cr = self.c_plugin_inst.compute_resource
        self.pfcon_client = pfcon.Client(cr.compute_url, cr.compute_auth_token)

        self.swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                          settings.SWIFT_CONNECTION_PARAMS)

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
        try:
            if plugin_type == 'ds':
                inputdirs.append(self.get_previous_output_path())
            else:
                inputdirs.append(self.manage_plugin_instance_app_empty_inputdir())
        except Exception:
            self.c_plugin_inst.status = 'cancelled'  # giving up
            self.save_plugin_instance_final_status()
            return

        d_unextpath_params, d_path_params = self.get_plugin_instance_path_parameters()
        for path_param_value in [param_value for param_value in d_path_params.values()]:
            # the value of each parameter of type 'path' is a string
            # representing a comma-separated list of paths in obj storage
            inputdirs = inputdirs + path_param_value.split(',')

        # create data file to transmit
        try:
            zip_file = self.create_zip_file(inputdirs)
        except Exception:
            self.c_plugin_inst.status = 'cancelled'  # giving up
            self.save_plugin_instance_final_status()
            return

        # create job description dictionary
        cmd_args = self.get_plugin_instance_app_cmd_args()
        cmd_path_flags = list(d_unextpath_params.keys()) + list(d_path_params.keys())
        job_descriptors = {
            'cmd_args': ' '.join(cmd_args),
            'cmd_path_flags': ','.join(cmd_path_flags),
            'auid': self.c_plugin_inst.owner.username,
            'number_of_workers': self.c_plugin_inst.number_of_workers,
            'cpu_limit': self.c_plugin_inst.cpu_limit,
            'memory_limit': self.c_plugin_inst.memory_limit,
            'gpu_limit': self.c_plugin_inst.gpu_limit,
            'image': plugin.dock_image,
            'selfexec': plugin.selfexec,
            'selfpath': plugin.selfpath,
            'execshell': plugin.execshell,
            'type': plugin_type
        }
        pfcon_url = self.pfcon_client.url
        job_id = self.str_job_id
        logger.info(f'Submitting job {job_id} to pfcon url -->{pfcon_url}<--, '
                    f'description: {json.dumps(job_descriptors, indent=4)}')
        try:
            d_resp = self._submit_job(job_id, job_descriptors, zip_file.getvalue())
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

    def _submit_job(self, job_id, job_descriptors, dfile, timeout=9000):
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
        return d_resp

    def check_plugin_instance_app_exec_status(self):
        """
        Check a plugin instance's app execution status. If the associated job's
        execution time exceeds the maximum set for the remote compute environment then
        the job is cancelled. Otherwise the job's execution status is fetched from the
        remote and if finished without error then the job's zip file is downloaded and
        unpacked and the output files registered with the DB. Finally a delete request
        is made to remove the job from the remote environment.
        """
        if self.c_plugin_inst.status == 'started':
            job_id = self.str_job_id

            delta_exec_time = timezone.now() - self.c_plugin_inst.start_date
            delta_seconds = delta_exec_time.total_seconds()
            max_exec_seconds = self.c_plugin_inst.compute_resource.max_job_exec_seconds
            if delta_seconds > max_exec_seconds:
                logger.error(f'[CODE13,{job_id}]: Error, job exceeded maximum execution '
                             f'time ({max_exec_seconds} seconds)')
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
        fnames = [f.fname.name for f in previous.files.all()]
        for i in range(20):  # loop to deal with eventual consistency
            try:
                l_ls = self.swift_manager.ls(output_path)
            except ClientException as e:
                logger.error(f'[CODE06,{job_id}]: Error while listing swift '
                             f'storage files in {output_path}, detail: {str(e)}')
            else:
                if all(obj in l_ls for obj in fnames):
                    return output_path
            time.sleep(3)
        logger.error(f'[CODE11,{job_id}]: Error while listing swift storage files in '
                     f'{output_path}, detail: Presumable eventual consistency problem')
        self.c_plugin_inst.error_code = 'CODE11'
        raise NameError('Presumable eventual consistency problem.')

    def get_plugin_instance_app_cmd_args(self):
        """
        Get the list of the plugin instance app's cmd arguments.
        """
        # append flags to save input meta data (passed options) and
        # output meta data (output description)
        app_args = ['--saveinputmeta', '--saveoutputmeta']
        # append the parameters to app's argument list
        for param_inst in self.l_plugin_inst_param_instances:
            param = param_inst.plugin_param
            value = param_inst.value
            if param.action == 'store':
                app_args.append(param.flag)
                if param.type == 'string' and not value:
                    value = "''"  # handle empty string as a valid value for a flag
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
            try:
                l_ls = self.swift_manager.ls(output_path)
            except ClientException as e:
                logger.error(f'[CODE06,{job_id}]: Error while listing swift '
                             f'storage files in {output_path}, detail: {str(e)}')
                self.c_plugin_inst.error_code = 'CODE06'
                raise
            if (i < len(regexs)) and regexs[i]:
                r = re.compile(regexs[i])
                d_objs[plg_inst.id] = {'output_path': output_path,
                                       'objs': [obj for obj in l_ls if r.search(obj)]}
            else:
                d_objs[plg_inst.id] = {'output_path': output_path,
                                       'objs': l_ls}
        return d_objs, group_by_instance

    def manage_plugin_instance_app_empty_inputdir(self):
        """
        This method is responsible for managing the 'inputdir' in the case of
        FS and TS plugins. FS and TS plugins do not have an inputdir spec, since this
        is only a requirement for DS plugins. Nonetheless, the remote services do
        require some non-zero inputdir spec in order to operate correctly.

        The hack here is to store data somewhere in swift and accessing it as a
        "pseudo" inputdir for FS and TS plugins. We create a "dummy" inputdir with a
        small dummy text file in swift storage. This is then transmitted as an 'inputdir'
        to the compute environment and can be completely ignored by the plugin.
        """
        job_id = self.str_job_id
        data_dir = os.path.join(os.path.expanduser("~"), 'data')
        str_inputdir = os.path.join(data_dir, 'squashEmptyDir').lstrip('/')
        str_squashFile = os.path.join(str_inputdir, 'squashEmptyDir.txt')
        str_squashMsg = 'Empty input dir.'
        try:
            if not self.swift_manager.obj_exists(str_squashFile):
                with io.StringIO(str_squashMsg) as f:
                    self.swift_manager.upload_obj(str_squashFile, f.read(),
                                                  content_type='text/plain')
        except ClientException as e:
            logger.error(f'[CODE07,{job_id}]: Error while uploading file '
                         f'{str_squashFile} to swift storage, detail: {str(e)}')
            self.c_plugin_inst.error_code = 'CODE07'
            raise
        return str_inputdir

    def create_zip_file(self, swift_paths):
        """
        Create job zip file ready for transmission to the remote from a list of swift
        storage paths (prefixes).
        """
        job_id = self.str_job_id
        memory_zip_file = io.BytesIO()
        # set_trace(host = "0.0.0.0", port = 6900, term_size = (252, 72))
        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_data_zip:
            for swift_path in swift_paths:
                try:
                    l_ls = self.swift_manager.ls(swift_path)
                except ClientException as e:
                    logger.error(f'[CODE06,{job_id}]: Error while listing swift '
                                 f'storage files in {swift_path}, detail: {str(e)}')
                    self.c_plugin_inst.error_code = 'CODE06'
                    raise
                for obj_path in l_ls:
                    try:
                        contents = self.swift_manager.download_obj(obj_path)
                    except ClientException as e:
                        logger.error(f'[CODE08,{job_id}]: Error while downloading file '
                                     f'{obj_path} from swift storage, detail: {str(e)}')
                        self.c_plugin_inst.error_code = 'CODE08'
                        raise
                    if 'pl.meta.json' in obj_path: obj_path = obj_path.replace(
                                                        'pl.meta.json',
                                                        'pl-parent.meta.json')
                    zip_path = obj_path.replace(swift_path, '', 1).lstrip('/')
                    job_data_zip.writestr(zip_path, contents)
        memory_zip_file.seek(0)
        return memory_zip_file

    def chrisEnvMetaFile_contents(self):
        '''
        Generate a "pl.meta.json" meta file, read contents into memory, and
        return the contents
        '''
        bytes                   = None
        # Meta data to capture...
        d_metaInfo      : dict  = {
            'jid'               : self.str_job_id,
            'previous_id'       : self.c_plugin_inst.previous_id,
            'id'                : self.c_plugin_inst.id
        }
        str_metaFile    : str   = '/tmp/%s.json' % self.str_job_id
        # First, save to file
        with open(str_metaFile, 'w') as fw:
            json.dump(d_metaInfo, fw, indent = 4)
        fw.close()
        # then, read the file into bytes
        fr      = open(str_metaFile, 'rb')
        if fr:
            bytes   = fr.read()
            os.remove(str_metaFile)
        return(bytes)

    def unpack_zip_file(self, zip_file_content):
        """
        Unpack job zip file from the remote into swift storage and register the
        extracted files with the DB.

        Inject at this point into the unpack file payload, a file called "chris.env"
        that contains some CUBE environmental information. This provides a test
        mechanism for communicating to a downstream plugin information about its
        parent, such as the parent's pluginInstanceID.
        """
        job_id = self.str_job_id
        swift_filenames = []
        # set_trace(host = "0.0.0.0", port = 6900, term_size = (252, 72))
        try:
            memory_zip_file = io.BytesIO(zip_file_content)
            with zipfile.ZipFile(memory_zip_file, 'r', zipfile.ZIP_DEFLATED) as job_zip:
                filenames = job_zip.namelist()
                filenames.append('pl.meta.json')
                logger.info(f'{len(filenames)} files to decompress for job {job_id}')
                output_path = self.c_plugin_inst.get_output_path() + '/'
                for fname in filenames:
                    if fname != 'pl.meta.json':
                        content = job_zip.read(fname)
                    else:
                        content = self.chrisEnvMetaFile_contents()
                    swift_fname = output_path + fname.lstrip('/')
                    # logger.info(f'fname {fname}; swift_fname {swift_fname}')
                    try:
                        self.swift_manager.upload_obj(swift_fname, content)
                    except ClientException as e:
                        logger.error(f'[CODE07,{job_id}]: Error while uploading file '
                                     f'{swift_fname} to swift storage, detail: {str(e)}')
                        self.c_plugin_inst.error_code = 'CODE07'
                        raise
                    swift_filenames.append(swift_fname)
        except ClientException:
            raise
        except Exception as e:
            logger.error(f'[CODE04,{job_id}]: Received bad zip file from remote, '
                         f'detail: {str(e)}')
            self.c_plugin_inst.error_code = 'CODE04'
            raise
        self._register_output_files(swift_filenames)

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
        Internal method to handle parameters of type 'unextpath' passed to the plugin
        instance app.
        """
        job_id = self.str_job_id
        outputdir = self.c_plugin_inst.get_output_path()
        obj_output_path_list = []
        for param_flag in unextpath_parameters_dict:
            # each parameter value is a string of one or more paths separated by comma
            path_list = unextpath_parameters_dict[param_flag].split(',')
            for path in path_list:
                try:
                    obj_list = self.swift_manager.ls(path)
                except ClientException as e:
                    logger.error(f'[CODE06,{job_id}]: Error while listing swift '
                                 f'storage files in {path}, detail: {str(e)}')
                    self.c_plugin_inst.error_code = 'CODE06'
                    raise
                for obj in obj_list:
                    obj_output_path = obj.replace(path.rstrip('/'), outputdir, 1)
                    if not obj_output_path.startswith(outputdir + '/'):
                        obj_output_path = outputdir + '/' + obj.split('/')[-1]
                    try:
                        if not self.swift_manager.obj_exists(obj_output_path):
                            self.swift_manager.copy_obj(obj, obj_output_path)
                    except ClientException as e:
                        logger.error(f'[CODE09,{job_id}]: Error while copying file '
                                     f'from {obj} to {obj_output_path} in swift storage, '
                                     f'detail: {str(e)}')
                        self.c_plugin_inst.error_code = 'CODE09'
                        raise
                    else:
                        obj_output_path_list.append(obj_output_path)
        logger.info('Registering output files not extracted from swift with job %s',
                    self.str_job_id)
        self._register_output_files(obj_output_path_list)

    def _handle_app_ts_unextracted_input_objs(self, d_ts_input_objs, group_by_instance):
        """
        Internal method to handle a 'ts' plugin's input instances' filtered objects
        (which are not extracted from object storage).
        """
        job_id = self.str_job_id
        outputdir = self.c_plugin_inst.get_output_path()
        obj_output_path_list = []
        for plg_inst_id in d_ts_input_objs:
            plg_inst_output_path = d_ts_input_objs[plg_inst_id]['output_path']
            obj_list = d_ts_input_objs[plg_inst_id]['objs']
            plg_inst_outputdir = outputdir
            if group_by_instance:
                plg_inst_outputdir = os.path.join(outputdir, str(plg_inst_id))
            for obj in obj_list:
                obj_output_path = obj.replace(plg_inst_output_path, plg_inst_outputdir, 1)
                try:
                    if not self.swift_manager.obj_exists(obj_output_path):
                        self.swift_manager.copy_obj(obj, obj_output_path)
                except ClientException as e:
                    logger.error(f'[CODE09,{job_id}]: Error while copying file '
                                 f'from {obj} to {obj_output_path} in swift storage, '
                                 f'detail: {str(e)}')
                    self.c_plugin_inst.error_code = 'CODE09'
                    raise
                obj_output_path_list.append(obj_output_path)
        logger.info("Registering 'ts' plugin's output files not extracted from swift with"
                    " job %s", self.str_job_id)
        self._register_output_files(obj_output_path_list)

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
            logger.info(f'Sending zip file request to pfcon url -->{pfcon_url}<-- '
                        f'for job {job_id}')
            try:
                zip_content = self._get_job_zip_data(job_id)
            except PfconRequestException as e:
                logger.error(f'[CODE03,{job_id}]: Error fetching zip from pfcon url '
                             f'-->{pfcon_url}<--, detail: {str(e)}')
                self.c_plugin_inst.error_code = 'CODE03'
                self.c_plugin_inst.status = 'cancelled'  # giving up
            else:
                # data successfully downloaded so update summary
                d_jobStatusSummary = json.loads(self.c_plugin_inst.summary)
                d_jobStatusSummary['pullPath']['status'] = True
                self.c_plugin_inst.summary = json.dumps(d_jobStatusSummary)

                logger.info('Registering output files from remote with job %s', job_id)
                self.c_plugin_inst.status = 'registeringFiles'
                self.c_plugin_inst.save()  # inform FE about status change
                try:
                    self.unpack_zip_file(zip_content)  # register files from remote

                    # register files from unextracted path parameters
                    d_unextpath_params, _ = self.get_plugin_instance_path_parameters()
                    if d_unextpath_params:
                        self._handle_app_unextpath_parameters(d_unextpath_params)

                    # register files from filtered input instance paths ('ts' plugins)
                    if self.c_plugin_inst.plugin.meta.type == 'ts':
                        d_ts_input_objs, tf = self.get_ts_plugin_instance_input_objs()
                        self._handle_app_ts_unextracted_input_objs(d_ts_input_objs, tf)
                except Exception:
                    self.c_plugin_inst.status = 'cancelled'  # giving up
                else:
                    self.c_plugin_inst.status = 'finishedSuccessfully'
            self.delete_plugin_instance_job_from_remote()
            self.save_plugin_instance_final_status()

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

    def _register_output_files(self, filenames):
        """
        Internal method to register output files generated for the plugin instance with
        the DB. The 'filenames' arg is a list of obj names in object storage.
        """
        job_id = self.str_job_id
        total_size = 0
        for obj_name in filenames:
            logger.info(f'Registering file -->{obj_name}<-- for job {job_id}')
            plg_inst_file = PluginInstanceFile(plugin_inst=self.c_plugin_inst)
            plg_inst_file.fname.name = obj_name
            try:
                plg_inst_file.save()
            except IntegrityError:  # avoid re-register a file already registered
                logger.info(f'File -->{obj_name}<-- already registered for job {job_id}')
            else:
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

            if len(logs) > 3000:
                d_jobStatusSummary['compute']['return']['job_logs'] = logs[-3000:]
        return json.dumps(d_jobStatusSummary)
