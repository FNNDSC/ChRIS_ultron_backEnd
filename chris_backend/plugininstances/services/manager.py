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
import io
import json
import zipfile
import requests
from requests.exceptions import Timeout, RequestException

from django.utils import timezone
from django.conf import settings
from django.db.utils import IntegrityError

from core.swiftmanager import SwiftManager, ClientException
from core.utils import json_zip2str
from plugininstances.models import PluginInstanceFile

if settings.DEBUG:
    import pdb, pudb, rpudb
    from celery.contrib import rdb


logger = logging.getLogger(__name__)


class PluginInstanceManager(object):

    def __init__(self, plugin_instance):

        self.c_plugin_inst = plugin_instance

        # hardcode mounting points for the input and outputdir in the app's container!
        self.str_app_container_inputdir = '/share/incoming'
        self.str_app_container_outputdir = '/share/outgoing'

        # some schedulers require a minimum job ID string length
        self.str_job_id = 'chris-jid-' + str(plugin_instance.id)

        self.swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                          settings.SWIFT_CONNECTION_PARAMS)

    def get_plugin_instance_app_cmd(self):
        """
        Get the plugin instance app's cmd, unextpath and path parameters in a tuple.
        """
        plugin = self.c_plugin_inst.plugin
        app_args = []
        path_parameters_dict = {}
        unextpath_parameters_dict = {}

        # append app's container input dir to app's argument list (only for ds plugins)
        if plugin.meta.type == 'ds':
            app_args.append(self.str_app_container_inputdir)
        # append app's container output dir to app's argument list
        app_args.append(self.str_app_container_outputdir)
        # append flag to save input meta data (passed options)
        app_args.append('--saveinputmeta')
        # append flag to save output meta data (output description)
        app_args.append('--saveoutputmeta')
        # append the parameters to app's argument list and identify
        # parameters of type 'unextpath' and 'path'
        param_instances = self.c_plugin_inst.get_parameter_instances()
        for param_inst in param_instances:
            param = param_inst.plugin_param
            value = param_inst.value
            if param.action == 'store':
                app_args.append(param.flag)
                if param.type == 'unextpath':
                    unextpath_parameters_dict[param.name] = value
                    value = self.str_app_container_inputdir
                if param.type == 'path':
                    path_parameters_dict[param.name] = value
                    value = self.str_app_container_inputdir  # + '/' + value
                app_args.append(value)
            if param.action == 'store_true' and value:
                app_args.append(param.flag)
            if param.action == 'store_false' and not value:
                app_args.append(param.flag)

        str_exec = os.path.join(plugin.selfpath, plugin.selfexec)
        l_appArgs = [str(s) for s in app_args]  # convert all arguments to string
        str_allCmdLineArgs = ' '.join(l_appArgs)
        str_cmd = '%s %s' % (str_exec, str_allCmdLineArgs)
        return str_cmd, unextpath_parameters_dict, path_parameters_dict

    def run_plugin_instance_app(self):
        """
        Run the plugin instance's app via a call to a remote service provider.
        """
        if self.c_plugin_inst.status == 'cancelled':
            return

        str_cmd, d_unextpath_params, d_path_params = self.get_plugin_instance_app_cmd()
        if self.c_plugin_inst.previous:
            # WARNING: 'ds' plugins can also have 'path' parameters!
            str_inputdir = self.c_plugin_inst.previous.get_output_path()
        elif len(d_path_params):
            # WARNING: Inputdir assumed to only be one of the 'path' parameters!
            path_list = next(iter(d_path_params.values())).split(',')
            str_inputdir = path_list[0].strip('/')
        else:
            # No parameter of type 'path' was submitted, input dir is empty
            str_inputdir = self.manage_fsplugin_instance_app_empty_inputdir()

        zip_file = self.create_zip_file([str_inputdir])  # create data file to transmit
        plugin = self.c_plugin_inst.plugin
        payload = {  # create json payload to transmit
            'jid': self.str_job_id,
            'cmd': '%s %s' % (plugin.execshell, str_cmd),
            'auid': self.c_plugin_inst.owner.username,
            'number_of_workers': str(self.c_plugin_inst.number_of_workers),
            'cpu_limit': str(self.c_plugin_inst.cpu_limit),
            'memory_limit': str(self.c_plugin_inst.memory_limit),
            'gpu_limit': str(self.c_plugin_inst.gpu_limit),
            'image': plugin.dock_image,
            'selfexec': plugin.selfexec,
            'selfpath': plugin.selfpath,
            'execshell': plugin.execshell,
        }
        remote_url = self.c_plugin_inst.compute_resource.compute_url + '/api/v1/'
        logger.info('sent POST to pfcon service url -->%s<--', remote_url)
        logger.info('payload sent: %s', json.dumps(payload, indent=4))
        try:
            r = requests.post(remote_url,
                              files={'data_file': zip_file.getvalue()},
                              data=payload,
                              timeout=30)
        except (Timeout, RequestException) as e:
            logging.error('error in talking to pfcon service, detail: %s', str(e))
            self.c_plugin_inst.status = 'waiting'  # CUBE will retry later
        else:
            if r.status_code == 200:
                logger.info('successful response from pfcon: %s', r.text)
                # handle parameters of type 'unextpath'
                self._handle_app_unextpath_parameters(d_unextpath_params)
                # update the job status and summary
                self.c_plugin_inst.status = 'started'
                d_jobStatusSummary = self.get_job_status_summary()  # initial status
                self.c_plugin_inst.summary = json.dumps(d_jobStatusSummary)
                d_resp = r.json()
                self.c_plugin_inst.raw = json_zip2str(d_resp)
            else:
                logger.error('error response from pfcon: %s', r.text)
                self.c_plugin_inst.status = 'waiting'  # CUBE will retry later
        self.c_plugin_inst.save()

    def check_plugin_instance_app_exec_status(self):
        """
        Check a plugin instance's app execution status. It connects to the remote
        service to determine job status and if finished without error then
        downloads and unpacks zip file and registers output files.
        """
        if self.c_plugin_inst.status == 'started':
            remote_url = self.c_plugin_inst.compute_resource.compute_url + '/api/v1/'
            remote_url = remote_url + self.str_job_id + '/'
            logger.info('sent GET status to pfcon service url -->%s<--', remote_url)
            try:
                r = requests.get(remote_url, timeout=30)
            except (Timeout, RequestException) as e:
                logging.error('error in talking to pfcon service, detail: %s', str(e))
                return self.c_plugin_inst.status  # return here, CUBE will retry later
            if r.status_code != 200:
                # could not get status (third party pman service inaccessible)
                logger.error('error response from pfcon: %s', r.text)
                return self.c_plugin_inst.status  # return here, CUBE will retry later

            logger.info('successful response from pfcon: %s', r.text)
            d_response = r.json()
            l_status = d_response['compute']['d_ret']['l_status']
            logger.info('Current job remote status = %s', l_status)
            logger.info('Current job DB status     = %s', self.c_plugin_inst.status)

            # save the job 'summary' and 'raw', important only update those fields
            # to avoid concurrency problems with the 'status' field!
            d_jobStatusSummary = self.get_job_status_summary(d_response)
            self.c_plugin_inst.summary = json.dumps(d_jobStatusSummary)
            self.c_plugin_inst.raw = json_zip2str(d_response)
            self.c_plugin_inst.save(update_fields=['summary', 'raw'])

            if 'finishedSuccessfully' in l_status:
                remote_url = remote_url + 'file/'
                logger.info('sent GET zip file to pfcon service url -->%s<--', remote_url)
                try:
                    r = requests.get(remote_url, timeout=30)  # download zip file
                except (Timeout, RequestException) as e:
                    logging.error('error in talking to pfcon service, detail: %s', str(e))
                    return self.c_plugin_inst.status  # return here, CUBE will retry later

                if r.status_code == 200:
                    # only one concurrent async task should get here
                    # data successfully downloaded so update summary
                    d_jobStatusSummary['pullPath']['status'] = True
                    self.c_plugin_inst.summary = json.dumps(d_jobStatusSummary)

                    logger.info("Registering output files from remote with CUBE")
                    self.c_plugin_inst.status = 'registeringFiles'
                    self.c_plugin_inst.save()   # inform FE about new instance status
                    swift_filenames = self.unpack_zip_file(r.content)
                    self._register_output_files(swift_filenames)

                    self.c_plugin_inst.status = 'finishedSuccessfully'
                    logger.info("Saving job DB status as '%s'", self.c_plugin_inst.status)
                    self.c_plugin_inst.end_date = timezone.now()
                    logger.info("Saving job DB end_date as '%s'",
                                self.c_plugin_inst.end_date)
                    self.c_plugin_inst.save()
            elif 'finishedWithError' in l_status:
                self.c_plugin_inst.status = 'finishedWithError'
                logger.info("Saving job DB status as '%s'", self.c_plugin_inst.status)
                self.c_plugin_inst.end_date = timezone.now()
                logger.info("Saving job DB end_date as '%s'", self.c_plugin_inst.end_date)
                self.c_plugin_inst.save()
        return self.c_plugin_inst.status

    def cancel_plugin_instance_app_exec(self):
        """
        Cancel a plugin instance's app execution. It connects to the remote service
        to cancel job.
        """
        pass

    def manage_fsplugin_instance_app_empty_inputdir(self):
        """
        This method is responsible for managing the 'inputdir' in the case of
        FS plugins.

        An FS plugin does not have an inputdir spec, since this is only a
        requirement for DS plugins. Nonetheless, the remote services do
        require some non-zero inputdir spec in order to operate correctly.

        The hack here is to store data somewhere in swift and accessing it as a
        "pseudo" inputdir for FS plugins. For example, if an FS plugin has no
        arguments of type 'path', then we create a "dummy" inputdir with a
        small dummy text file in swift storage. This is then transmitted as an
        'inputdir' to the compute environment, and can be completely ignored by
        the plugin.
        """
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
            logger.error('Swift storage error, detail: %s' % str(e))
        return str_inputdir

    def create_zip_file(self, swift_paths):
        """
        Create job zip file ready for transmission to the remote from a list of swift
        storage paths (prefixes).
        """
        memory_zip_file = io.BytesIO()
        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_data_zip:
            for swift_path in swift_paths:
                l_ls = []
                try:
                    l_ls = self.swift_manager.ls(swift_path)
                except ClientException as e:
                    msg = 'Listing of swift storage files in %s failed, detail: %s' % (
                    swift_path, str(e))
                    logger.error(msg)
                for obj_path in l_ls:
                    try:
                        contents = self.swift_manager.download_obj(obj_path)
                    except ClientException as e:
                        msg = 'Downloading of file %s from swift storage for %s job ' \
                              'failed, detail: %s' % (obj_path, self.str_job_id, str(e))
                        logger.error(msg)
                    zip_path = obj_path.replace(swift_path, '', 1).lstrip('/')
                    job_data_zip.writestr(zip_path, contents)
        memory_zip_file.seek(0)
        return memory_zip_file

    def unpack_zip_file(self, zip_file_content):
        """
        Unpack job zip file from the remote into swift storage.
        """
        job_data_zip = zipfile.ZipFile(io.BytesIO(zip_file_content))
        filenames = job_data_zip.namelist()
        output_path = self.c_plugin_inst.get_output_path() + '/'
        swift_filenames = []
        for fname in filenames:
            content = job_data_zip.read(fname)
            swift_fname = output_path + fname.lstrip('/')
            swift_filenames.append(swift_fname)
            self.swift_manager.upload_obj(swift_fname, content)
        return swift_filenames

    def _handle_app_unextpath_parameters(self, unextpath_parameters_dict):
        """
        Handle parameters of type 'unextpath' passed to the plugin instance app.
        """
        outputdir = self.c_plugin_inst.get_output_path()
        obj_output_path_list = []
        for param_name in unextpath_parameters_dict:
            # each parameter value is a string of one or more paths separated by comma
            path_list = unextpath_parameters_dict[param_name].split(',')
            for path in path_list:
                obj_list = []
                try:
                    obj_list = self.swift_manager.ls(path)
                except ClientException as e:
                    logger.error('Swift storage error, detail: %s' % str(e))
                for obj in obj_list:
                    obj_output_path = obj.replace(path.rstrip('/'), outputdir, 1)
                    if not obj_output_path.startswith(outputdir + '/'):
                        obj_output_path = outputdir + '/' + obj.split('/')[-1]
                    try:
                        self.swift_manager.copy_obj(obj, obj_output_path)
                    except ClientException as e:
                        logger.error('Swift storage error, detail: %s' % str(e))
                    else:
                        obj_output_path_list.append(obj_output_path)
        logger.info("Registering output files not extracted from swift with CUBE")
        self._register_output_files(obj_output_path_list)

    def _register_output_files(self, filenames):
        """
        Register files generated by the plugin instance object with the REST API.
        The 'filenames' arg is a list of obj names in object storage.
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
        Get a job status summary dictionary from pfcon response.
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
                    'l_status': [],
                    'l_logs': []
                }
            },
        }
        if d_response is not None:
            d_c = d_response['compute']
            d_jobStatusSummary['compute']['return']['status'] = d_c['status']
            d_jobStatusSummary['compute']['return']['l_status'] = d_c['d_ret']['l_status']
            d_jobStatusSummary['compute']['return']['l_logs'] = d_c['d_ret']['l_logs']
            try:
                logs = d_jobStatusSummary['compute']['return']['l_logs'][0]
                if len(logs) > 3000:
                    d_jobStatusSummary['compute']['return']['l_logs'][0] = logs[-3000:]
            except Exception:
                logger.info('Compute logs not currently available.')
        return d_jobStatusSummary
