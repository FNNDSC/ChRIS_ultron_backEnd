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
import json
import zipfile
from pfconclient import client as pfcon
from pfconclient.exceptions import PfconRequestException

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


logger = logging.getLogger(__name__)


class PluginInstanceManager(object):

    def __init__(self, plugin_instance):

        self.c_plugin_inst = plugin_instance

        self.l_plugin_inst_param_instances = self.c_plugin_inst.get_parameter_instances()

        self.str_job_id = ChrisInstance.load().job_id_prefix + str(plugin_instance.id)

        self.pfcon_client = pfcon.Client(plugin_instance.compute_resource.compute_url)

        self.swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                          settings.SWIFT_CONNECTION_PARAMS)

    def run_plugin_instance_app(self):
        """
        Run the plugin instance's app via a call to a remote pfcon service.
        """
        if self.c_plugin_inst.status == 'cancelled':
            return

        plugin = self.c_plugin_inst.plugin
        plugin_type = plugin.meta.type
        inputdirs = []
        if plugin_type == 'ds':
            inputdirs.append(self.c_plugin_inst.previous.get_output_path())
        else:
            inputdirs.append(self.manage_plugin_instance_app_empty_inputdir())

        d_unextpath_params, d_path_params = self.get_plugin_instance_path_parameters()
        for path_param_value in [param_value for param_value in d_path_params.values()]:
            # the value of each parameter of type 'path' is a string
            # representing a comma-separated list of paths in obj storage
            inputdirs = inputdirs + path_param_value.split(',')

        # create data file to transmit
        zip_file = self.create_zip_file(inputdirs)

        # create job description dictionary
        cmd_args = self.get_plugin_instance_app_cmd_args()
        cmd_path_flags = list(d_unextpath_params.keys()) + list(d_path_params.keys())
        job_descriptors = {
            'cmd_args': ' '.join(cmd_args),
            'cmd_path_flags': ','.join(cmd_path_flags),
            'auid': self.c_plugin_inst.owner.username,
            'number_of_workers': str(self.c_plugin_inst.number_of_workers),
            'cpu_limit': str(self.c_plugin_inst.cpu_limit),
            'memory_limit': str(self.c_plugin_inst.memory_limit),
            'gpu_limit': str(self.c_plugin_inst.gpu_limit),
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
            d_resp = self.pfcon_client.submit_job(job_id, job_descriptors,
                                                  zip_file.getvalue(), timeout=1000)
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

    def check_plugin_instance_app_exec_status(self):
        """
        Check a plugin instance's app execution status. It connects to the remote
        service to determine job status and if finished without error then
        downloads and unpacks zip file and registers output files.
        """
        if self.c_plugin_inst.status == 'started':
            pfcon_url = self.pfcon_client.url
            job_id = self.str_job_id
            logger.info(f'Sending job status request to pfcon url -->{pfcon_url}<-- for '
                        f'job {job_id}')
            try:
                d_resp = self.pfcon_client.get_job_status(job_id, timeout=1000)
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

    def cancel_plugin_instance_app_exec(self):
        """
        Cancel a plugin instance's app execution. It connects to the remote service
        to cancel job.
        """
        pass

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
        Get a dictionary with keys that are the output dir of each input plugin instance
        to this 'ts' plugin instance. The values of this dictionary are lists of all the
        objects under the corresponding output dir key that match a filter for each of
        the provided plugin instances.
        """
        job_id = self.str_job_id
        # extract the 'ts' plugin's special parameters from the DB
        plg_inst_ids = regexs = []
        if self.c_plugin_inst.plugin.meta.type == 'ts':
            for param_inst in self.l_plugin_inst_param_instances:
                if param_inst.plugin_param.name == 'plugininstances':
                    # string param that represents a comma-separated list of ids
                    plg_inst_ids = param_inst.value.split(',') if param_inst.value else []
                elif param_inst.plugin_param.name == 'filter':
                    # string param that represents a comma-separated list of regular expr
                    regexs = param_inst.value.split(',') if param_inst.value else []
        d_objs = {}
        for i, inst_id in enumerate(plg_inst_ids):
            try:
                plg_inst = PluginInstance.objects.get(pk=int(inst_id))
            except PluginInstance.DoesNotExist:
                logger.error(f"[CODE05,{job_id}]: Couldn't find any plugin instance with "
                             f"id {inst_id} while processing input instances to 'ts' "
                             f"plugin instance with id {self.c_plugin_inst.id}")
            else:
                output_path = plg_inst.get_output_path()
                try:
                    l_ls = self.swift_manager.ls(output_path)
                except ClientException as e:
                    logger.error(f'[CODE06,{job_id}]: Error while listing swift '
                                 f'storage files in {output_path}, detail: {str(e)}')
                else:
                    if (i < len(regexs)) and regexs[i]:
                        r = re.compile(regexs[i])
                        d_objs[output_path] = [obj for obj in l_ls if r.search(obj)]
                    else:
                        d_objs[output_path] = l_ls
        return d_objs

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
        return str_inputdir

    def create_zip_file(self, swift_paths):
        """
        Create job zip file ready for transmission to the remote from a list of swift
        storage paths (prefixes).
        """
        job_id = self.str_job_id
        memory_zip_file = io.BytesIO()
        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_data_zip:
            for swift_path in swift_paths:
                l_ls = []
                try:
                    l_ls = self.swift_manager.ls(swift_path)
                except ClientException as e:
                    logger.error(f'[CODE06,{job_id}]: Error while listing swift '
                                 f'storage files in {swift_path}, detail: {str(e)}')
                for obj_path in l_ls:
                    try:
                        contents = self.swift_manager.download_obj(obj_path)
                    except ClientException as e:
                        logger.error(f'[CODE08,{job_id}]: Error while downloading file '
                                     f'{obj_path} from swift storage, detail: {str(e)}')
                    zip_path = obj_path.replace(swift_path, '', 1).lstrip('/')
                    job_data_zip.writestr(zip_path, contents)
        memory_zip_file.seek(0)
        return memory_zip_file

    def unpack_zip_file(self, zip_file_content):
        """
        Unpack job zip file from the remote into swift storage.
        """
        job_id = self.str_job_id
        swift_filenames = []
        memory_zip_file = io.BytesIO(zip_file_content)
        with zipfile.ZipFile(memory_zip_file, 'r', zipfile.ZIP_DEFLATED) as job_data_zip:
            filenames = job_data_zip.namelist()
            logger.info('Number of files to decompress %s: ', len(filenames))
            output_path = self.c_plugin_inst.get_output_path() + '/'
            for fname in filenames:
                content = job_data_zip.read(fname)
                swift_fname = output_path + fname.lstrip('/')
                swift_filenames.append(swift_fname)
                try:
                    self.swift_manager.upload_obj(swift_fname, content)
                except ClientException as e:
                    logger.error(f'[CODE07,{job_id}]: Error while uploading file '
                                 f'{swift_fname} to swift storage, detail: {str(e)}')
        return swift_filenames

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
                obj_list = []
                try:
                    obj_list = self.swift_manager.ls(path)
                except ClientException as e:
                    logger.error(f'[CODE06,{job_id}]: Error while listing swift '
                                 f'storage files in {path}, detail: {str(e)}')
                for obj in obj_list:
                    obj_output_path = obj.replace(path.rstrip('/'), outputdir, 1)
                    if not obj_output_path.startswith(outputdir + '/'):
                        obj_output_path = outputdir + '/' + obj.split('/')[-1]
                    try:
                        self.swift_manager.copy_obj(obj, obj_output_path)
                    except ClientException as e:
                        logger.error(f'[CODE09,{job_id}]: Error while copying file '
                                     f'from {obj} to {obj_output_path} in swift storage, '
                                     f'detail: {str(e)}')
                    else:
                        obj_output_path_list.append(obj_output_path)
        logger.info('Registering output files not extracted from swift with job %s',
                    self.str_job_id)
        self._register_output_files(obj_output_path_list)

    def _handle_app_ts_unextracted_input_objs(self, d_ts_input_objs):
        """
        Internal method to handle a 'ts' plugin's input instances' filtered objects
        that are not extracted from object storage.
        """
        job_id = self.str_job_id
        outputdir = self.c_plugin_inst.get_output_path()
        obj_output_path_list = []
        for plg_inst_outputdir in d_ts_input_objs:
            obj_list = d_ts_input_objs[plg_inst_outputdir]
            for obj in obj_list:
                obj_output_path = obj.replace(plg_inst_outputdir, outputdir, 1)
                try:
                    self.swift_manager.copy_obj(obj, obj_output_path)
                except ClientException as e:
                    logger.error(f'[CODE09,{job_id}]: Error while copying file '
                                 f'from {obj} to {obj_output_path} in swift storage, '
                                 f'detail: {str(e)}')
                else:
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
                zip_content = self.pfcon_client.get_job_zip_data(job_id, 1000)
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
                    swift_filenames = self.unpack_zip_file(zip_content)
                except Exception as e:
                    logger.error(f'[CODE04,{job_id}]: Received bad zip file from remote, '
                                 f'detail: {str(e)}')
                    self.c_plugin_inst.error_code = 'CODE04'
                    self.c_plugin_inst.status = 'cancelled'  # giving up
                else:
                    self._register_output_files(swift_filenames)

                    # handle unextracted path parameters
                    d_unextpath_params, _ = self.get_plugin_instance_path_parameters()
                    if d_unextpath_params:
                        self._handle_app_unextpath_parameters(d_unextpath_params)

                    # handle filtered paths from input instances for 'ts' plugin instances
                    if self.c_plugin_inst.plugin.meta.type == 'ts':
                        d_ts_input_objs = self.get_ts_plugin_instance_input_objs()
                        self._handle_app_ts_unextracted_input_objs(d_ts_input_objs)

                    self.c_plugin_inst.status = 'finishedSuccessfully'
            self.save_plugin_instance_final_status()

    def _handle_finished_with_error_status(self):
        """
        Internal method to handle the 'finishedWithError' status returned by the
        remote compute.
        """
        self.c_plugin_inst.status = 'finishedWithError'
        self.save_plugin_instance_final_status()

    def _handle_undefined_status(self):
        """
        Internal method to handle the 'undefined' status returned by the
        remote compute.
        """
        job_id = self.str_job_id
        logger.error(f'[CODE10,{job_id}]: Got undefined status from remote')
        self.c_plugin_inst.error_code = 'CODE10'
        self.c_plugin_inst.status = 'cancelled'
        self.save_plugin_instance_final_status()

    def _register_output_files(self, filenames):
        """
        Internal method to register files generated by the plugin instance object with
        the REST API. The 'filenames' arg is a list of obj names in object storage.
        """
        for obj_name in filenames:
            logger.info('Registering  -->%s<--', obj_name)
            plg_inst_file = PluginInstanceFile(plugin_inst=self.c_plugin_inst)
            plg_inst_file.fname.name = obj_name
            try:
                plg_inst_file.save()
            except IntegrityError:  # avoid re-register a file already registered
                logger.info('-->%s<-- already registered', obj_name)

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
