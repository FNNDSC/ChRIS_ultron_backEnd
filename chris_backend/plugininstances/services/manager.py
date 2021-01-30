"""
Plugin instance app manager module that provides functionality to run and check the
execution status of a plugin instance's app (ChRIS / pfcon interface).

NOTE:

    This module is now executed as part of an asynchronous celery worker.
    For instance, to debug 'check_plugin_instance_app_exec_status' method synchronously
    with pudb.set_trace() you need to:

    1. Once CUBE is running, and assuming some plugininstance has been POSTed, start a
    python shell on the manage.py code (note <IMAGE> below is the chris:dev container):

    docker exec -ti <IMAGE> python manage.py shell

    You should now be in a python shell.

    3. To simulate operations on a given plugin with id <id>,
    instantiate the relevant objects (for ex, for id=1):

    from plugininstances.models import PluginInstance
    from plugininstances.services import manager

    plg_inst = PluginInstance.objects.get(id=1)
    plg_inst_manager = manager.PluginInstanceManager(plg_inst)

    4. And finally, call the method:

    plg_inst_manager.check_plugin_instance_app_exec_status()

    Any pudb.set_trace() calls in this method will now be handled by the pudb debugger.

    5. Finally, after each change to this method, reload this module:

    import importlib
    importlib.reload(manager)

    and also re-instantiate the service:

    plg_inst_manager = manager.PluginInstanceManager(plg_inst)
"""

import logging
import os
import io
import json
import zlib, base64
import zipfile

from django.utils import timezone
from django.conf import settings

import pfurl
import time
import json

from core.swiftmanager import SwiftManager, ClientException

if settings.DEBUG:
    import pdb
    import pudb
    import rpudb
    from celery.contrib import rdb


logger = logging.getLogger(__name__)


class PluginInstanceManager(object):

    def __init__(self, plugin_instance):

        self.c_plugin_inst = plugin_instance

        # hardcode mounting points for the input and outputdir in the app's container!
        self.str_app_container_inputdir     = '/share/incoming'
        self.str_app_container_outputdir    = '/share/outgoing'

        # some schedulers require a minimum job ID string length
        self.str_job_id = settings.CHRIS_JID_PREFIX + str(plugin_instance.id)

        # local data dir to store zip files before transmitting to the remote
        self.data_dir = os.path.join(os.path.expanduser("~"), 'data')

        self.swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                          settings.SWIFT_CONNECTION_PARAMS)

    def run_plugin_instance_app(self):
        """
        Run a plugin instance's app via a call to a remote service provider.
        """
        if self.c_plugin_inst.status == 'cancelled':
            return self.c_plugin_inst.status

        plugin = self.c_plugin_inst.plugin
        app_args = []
        # append app's container input dir to app's argument list (only for ds plugins)
        if plugin.meta.type == 'ds':
            app_args.append(self.str_app_container_inputdir)
        # append app's container output dir to app's argument list
        app_args.append(self.str_app_container_outputdir)
        # append flag to save input meta data (passed options)
        app_args.append("--saveinputmeta")
        # append flag to save output meta data (output description)
        app_args.append("--saveoutputmeta")
        # append the parameters to app's argument list and identify
        # parameters of type 'unextpath' and 'path'
        path_parameters_dict = {}
        unextpath_parameters_dict = {}
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
                    value = self.str_app_container_inputdir
                app_args.append(value)
            if param.action == 'store_true' and value:
                app_args.append(param.flag)
            if param.action == 'store_false' and not value:
                app_args.append(param.flag)

        str_outputdir = self.c_plugin_inst.get_output_path()

        # handle parameters of type 'unextpath'
        self.handle_app_unextpath_parameters(unextpath_parameters_dict)

        if self.c_plugin_inst.previous:
            # WARNING: 'ds' plugins can also have 'path' parameters!
            str_inputdir = self.c_plugin_inst.previous.get_output_path()
        elif len(path_parameters_dict):
            # WARNING: Inputdir assumed to only be one of the 'path' parameters!
            path_list = next(iter(path_parameters_dict.values())).split(',')
            str_inputdir = path_list[0].strip('/')
        else:
            # No parameter of type 'path' was submitted, input dir is empty
            str_inputdir = self.manage_app_service_fsplugin_empty_inputdir()

        str_exec = os.path.join(plugin.selfpath, plugin.selfexec)
        l_appArgs = [str(s) for s in app_args]  # convert all arguments to string
        str_allCmdLineArgs = ' '.join(l_appArgs)
        str_cmd = '%s %s' % (str_exec, str_allCmdLineArgs)
        logger.info('cmd = %s', str_cmd)

        # logger.debug('d_pluginInst = %s', vars(self.c_plugin_inst))
        str_IOPhost = self.c_plugin_inst.compute_resource.name
        d_msg = {
            "action": "coordinate",
            "threadAction": True,
            "meta-store":
                {
                    "meta": "meta-compute",
                    "key": "jid"
                },

            "meta-data":
                {
                    "remote":
                        {
                            "key": "%meta-store"
                        },
                    "localSource":
                        {
                            "path": str_inputdir,
                            "storageType": "swift"
                        },
                    "localTarget":
                        {
                            "path": str_outputdir,
                            "createDir": True
                        },
                    "specialHandling":
                        {
                            "op": "plugin",
                            "cleanup": True
                        },
                    "transport":
                        {
                            "mechanism": "compress",
                            "compress":
                                {
                                    "archive": "zip",
                                    "unpack": True,
                                    "cleanup": True
                                }
                        },
                    "service": str_IOPhost
                },

            "meta-compute":
                {
                    'cmd': "%s %s" % (plugin.execshell, str_cmd),
                    'threaded': True,
                    'auid': self.c_plugin_inst.owner.username,
                    'jid': self.str_job_id,
                    'number_of_workers': str(self.c_plugin_inst.number_of_workers),
                    'cpu_limit': str(self.c_plugin_inst.cpu_limit),
                    'memory_limit': str(self.c_plugin_inst.memory_limit),
                    'gpu_limit': str(self.c_plugin_inst.gpu_limit),
                    "container":
                        {
                            "target":
                                {
                                    "image": plugin.dock_image,
                                    "cmdParse": False,
                                    "selfexec": plugin.selfexec,
                                    "selfpath": plugin.selfpath,
                                    "execshell": plugin.execshell
                                },
                            "manager":
                                {
                                    "image": "fnndsc/swarm",
                                    "app": "swarm.py",
                                    "env":
                                        {
                                            "meta-store": "key",
                                            "serviceType": "docker",
                                            "shareDir": "%shareDir",
                                            "serviceName": self.str_job_id
                                        }
                                }
                        },
                    "service": str_IOPhost
                }
        }
        self.call_app_service(d_msg)
        self.c_plugin_inst.status = 'started'
        self.c_plugin_inst.save()

    def handle_app_unextpath_parameters(self, unextpath_parameters_dict):
        """
        Handle parameters of type 'unextpath' passed to the plugin instance app.
        """
        outputdir = self.c_plugin_inst.get_output_path()
        nobjects = 0
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
                        nobjects += 1
        #swiftState = {'d_swiftstore': {'filesPushed': nobjects}}
        #self.c_plugin_inst.register_output_files(swiftState=swiftState)

    def check_plugin_instance_app_exec_status(self):
        """
        Check a plugin instance's app execution status. It connects to the remote
        service to determine job status and if just finished without error,
        register output files.
        """

        if self.c_plugin_inst.status == 'cancelled':
            return self.c_plugin_inst.status

        if self.c_plugin_inst.status == 'started':
            d_msg = {
                "action": "status",
                "meta": {
                        "remote": {
                            "key": self.str_job_id
                        }
                }
            }
            d_response = self.call_app_service(d_msg)
            l_status = d_response['jobOperationSummary']['compute']['return']['l_status']
            logger.info('Current job remote status = %s', l_status)
            logger.info('Current job DB status     = %s', self.c_plugin_inst.status)

            str_responseStatus = self.serialize_app_response_status(d_response)
            if 'swiftPut:True' in str_responseStatus:
                logger.info("Registering swift objects to CUBE")
                d_swiftState = d_response['jobOperation']['info']['swiftPut']
                logger.info("swiftState = %s" % json.dumps(d_swiftState, indent = 4))
                # This setting of status protects against unnecessary concurrent
                # collisions on `register_output_files()` and better informs the FE
                self.c_plugin_inst.status = 'registeringFiles'
                self.c_plugin_inst.save()
                d = self.c_plugin_inst.register_output_files(swiftState=d_swiftState)
                # Once the `register_output_files` is done, we can set
                # the proper finall state
                if d['status']:
                    self.c_plugin_inst.status = 'finishedSuccessfully'
                else:
                    self.c_plugin_inst.status = 'finishedWithError'
                logger.info("Saving job DB status as '%s'", self.c_plugin_inst.status)
                self.c_plugin_inst.end_date = timezone.now()
                logger.info("Saving job DB end_date as '%s'", self.c_plugin_inst.end_date)
                self.c_plugin_inst.save()

            # Some possible error handling...
            if 'finishedWithError' in l_status:
                self.c_plugin_inst.status = 'finishedWithError'
                logger.info("Saving job DB status as '%s'", self.c_plugin_inst.status)
                self.c_plugin_inst.end_date = timezone.now()
                logger.info("Saving job DB end_date as '%s'", self.c_plugin_inst.end_date)
                self.c_plugin_inst.save()
                self.handle_app_remote_error()
        return self.c_plugin_inst.status

    def cancel_plugin_instance_app_exec(self):
        """
        Cancel a plugin instance's app execution. It connects to the remote service
        to cancel job.
        """
        pass

    def call_app_service(self, d_msg):
        """
        This method sends the JSON 'msg' argument to the remote service.
        """
        remote_url = self.c_plugin_inst.compute_resource.compute_url
        serviceCall = pfurl.Pfurl(
            msg                     = json.dumps(d_msg),
            http                    = remote_url,
            verb                    = 'POST',
            # contentType             = 'application/json',
            b_raw                   = True,
            b_quiet                 = True,
            b_httpResponseBodyParse = True,
            jsonwrapper             = 'payload',
        )
        logger.info('comms sent to pfcon service at -->%s<--', remote_url)
        logger.info('message sent: %s', json.dumps(d_msg, indent=4))

        # Leave here for now... might be useful for later debugging.
        # with open('/tmp/%d-%s-%s.json' % \
        #          (time.time_ns() // 1000000,
        #           d_msg['action'],
        #           self.str_job_id), 'w') as l:
        #          json.dump(d_msg, l, indent = 4)

        # logger.debug('comms sent to pfcon service at -->%s<--', remote_url)
        # logger.debug('message sent: %s', json.dumps(d_msg, indent=4))

        # try:
        #     rpudb.set_trace(addr='0.0.0.0', port=7901)
        # except:
        #     pudb.set_trace()
        d_response = json.loads(serviceCall())

        if isinstance(d_response, dict):
            logger.info('looks like we got a successful response from pfcon service')
            logger.info('response from pfurl(): %s', json.dumps(d_response, indent=4))
        else:
            logger.info('looks like we got an UNSUCCESSFUL response from pfcon service')
            logger.info('response from pfurl(): -->%s<--', d_response)
        if "Connection refused" in d_response:
            logging.error('fatal error in talking to pfcon service')
        return d_response

    def manage_app_service_fsplugin_empty_inputdir(self):
        """
        This method is responsible for managing the 'inputdir' in the case of
        FS plugins.

        An FS plugin does not have an inputdir spec, since this is only a
        requirement for DS plugins. Nonetheless, the underlying management
        system (pfcon/pfurl) does require some non-zero inputdir spec in order
        to operate correctly.

        The hack here is to store data somewhere in swift and accessing it as a
        "pseudo" inputdir for FS plugins. For example, if an FS plugin has no
        arguments of type 'path', then we create a "dummy" inputdir with a
        small dummy text file in swift storage. This is then transmitted as an
        'inputdir' to the compute environment, and can be completely ignored by
        the plugin.

        Importantly, one major exception to the normal FS processing scheme
        exists: an FS plugin that collects data from object storage. This
        storage location is not an 'inputdir' in the traditional sense, and is
        thus specified in the FS plugin argument list as argument of type
        'path' (i.e. there is no positional argument for inputdir as in DS
        plugins). Thus, if a type 'path' argument is specified, this 'path'
        is assumed to denote a location in object storage.
        """
        str_inputdir = os.path.join(self.data_dir, 'squashEmptyDir').lstrip('/')
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

    def serialize_app_response_status(self, d_response):
        """
        Serialize and save the 'jobOperation' and 'jobOperationSummary'.
        """
        # Still WIP about what is best summary...

        try:
            str_logsFromCompute = d_response['jobOperationSummary'] \
                ['compute'] \
                ['return'] \
                ['l_logs'][0]

            if len(str_logsFromCompute) > 3000:
                d_response['jobOperationSummary'] \
                    ['compute'] \
                    ['return'] \
                    ['l_logs'][0] = str_logsFromCompute[-3000:]
        except Exception:
            logger.info('Compute logs not currently available.')

        # update plugin instance with status info
        self.c_plugin_inst.summary = json.dumps(d_response['jobOperationSummary'])
        self.c_plugin_inst.raw = self.json_zipToStr(d_response['jobOperation'])
        self.c_plugin_inst.save()

        str_responseStatus = ""
        for str_action in ['pushPath', 'compute', 'pullPath', 'swiftPut']:
            if str_action == 'compute':
                for str_part in ['submit', 'return']:
                    str_actionStatus = str(d_response['jobOperationSummary'] \
                                               [str_action] \
                                               [str_part] \
                                               ['status'])
                    str_actionStatus = ''.join(str_actionStatus.split())
                    str_responseStatus += str_action + '.' + str_part + ':' + \
                                          str_actionStatus + ';'
            else:
                str_actionStatus = str(d_response['jobOperationSummary'] \
                                           [str_action] \
                                           ['status'])
                str_actionStatus = ''.join(str_actionStatus.split())
                str_responseStatus += str_action + ':' + str_actionStatus + ';'
        return str_responseStatus

    def handle_app_remote_error(self):
        """
        Collect the 'stderr' from the remote app.
        """
        str_deepVal = ''
        def str_deepnest(d):
            nonlocal str_deepVal
            if d:
                for k, v in d.items():
                    if isinstance(v, dict):
                        str_deepnest(v)
                    else:
                        str_deepVal = '%s' % ("{0} : {1}".format(k, v))

        # Collect the 'stderr' from the app service for this instance
        d_msg = {
            "action": "search",
            "meta": {
                "key": "jid",
                "value": self.str_job_id,
                "job": "0",
                "when": "end",
                "field": "stderr"
            }
        }
        d_response = self.call_app_service(d_msg)
        str_deepnest(d_response)
        logger.error('deepVal = %s', str_deepVal)

        d_msg['meta']['field'] = 'returncode'
        d_response = self.call_app_service(d_msg)
        str_deepnest(d_response)
        logger.error('deepVal = %s', str_deepVal)

    def create_zip_file(self, swift_paths):
        """
        Create job zip file ready for transmission to the remote from a list of swift
        storage paths (prefixes).
        """
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)  # create data dir
            except OSError as e:
                msg = 'Creation of dir %s failed, detail: %s' % (self.data_dir, str(e))
                logger.error(msg)

        zipfile_path = os.path.join(self.data_dir, self.str_job_id + '.zip')
        with zipfile.ZipFile(zipfile_path, 'w', zipfile.ZIP_DEFLATED) as job_data_zip:
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
                    job_data_zip.writestr(obj_path, contents)

    @staticmethod
    def json_zipToStr(json_data):
        """
        Return a string of compressed JSON data, suitable for transmission
        back to a client.
        """
        return base64.b64encode(
            zlib.compress(
                json.dumps(json_data).encode('utf-8')
            )
        ).decode('ascii')
