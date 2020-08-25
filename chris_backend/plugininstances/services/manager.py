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
import time
import json
import zlib, base64

from django.utils import timezone
from django.conf import settings

import pfurl

from core.swiftmanager import SwiftManager

if settings.DEBUG:
    import pdb
    import pudb
    from celery.contrib import rdb


logger = logging.getLogger(__name__)


class PluginInstanceManager(object):

    def __init__(self, plugin_instance):

        # hardcode mounting points for the input and outputdir in the app's container!
        self.str_app_container_inputdir = '/share/incoming'
        self.str_app_container_outputdir = '/share/outgoing'

        # A job ID prefix string. Necessary since some schedulers require
        # a minimum job ID string length
        self.str_jid_prefix = 'chris-jid-'

        self.c_plugin_inst = plugin_instance
        self.swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                          settings.SWIFT_CONNECTION_PARAMS)

    def run_plugin_instance_app(self, parameter_dict):
        """
        Run a plugin instance's app via a call to a remote service provider.
        """
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
        # append the parameters to app's argument list and identify 'path' type parameters
        path_param_names = []
        unextpath_param_names = []
        db_parameters = plugin.parameters.all()
        for param_name in parameter_dict:
            param_value = parameter_dict[param_name]
            for db_param in db_parameters:
                if db_param.name == param_name:
                    if db_param.action == 'store':
                        app_args.append(db_param.flag)
                        value = param_value
                        if db_param.type == 'unextpath':
                            unextpath_param_names.append(param_name)
                            value = self.str_app_container_inputdir
                        if db_param.type == 'path':
                            path_param_names.append(param_name)
                            value = self.str_app_container_inputdir
                        app_args.append(value)
                    if db_param.action == 'store_true' and param_value:
                        app_args.append(db_param.flag)
                    if db_param.action == 'store_false' and not param_value:
                        app_args.append(db_param.flag)
                    break

        # Handle the case for 'fs'-type plugins that don't specify an inputdir
        # Passing an empty string through to pfurl will cause it to fail
        # on its local directory check. The "hack" here is that the manager will
        # "transparently" set the input dir to a location in swift in the case of
        # FS-type plugins
        #
        #       /home/localuser/data/squashEmptyDir
        #
        # which in turn contains a "file"
        #
        #       /home/localuser/data/squashEmptyDir/squashEmptyDir.txt
        #
        # This "inputdir" is then sent along with `pfcon/pfurl` and is of
        # course ignored by the actual plugin when it is run. This does have
        # the anti-pattern side effect of possibly using this to send
        # completely OOB (out of band) data to an FS plugin in this "fake"
        # "inputdir" and could have implications. Right now though I don't
        # see how an FS plugin could even access this fake "inputdir".
        #
        if self.c_plugin_inst.previous:
            # WARNING: 'ds' plugins can also have 'path' parameters!
            str_inputdir = self.c_plugin_inst.previous.get_output_path()
        else:
            # WARNING: Inputdir assumed to only be the last 'path' parameter!
            str_inputdir = parameter_dict[path_param_names[-1]] if path_param_names else ''
            str_inputdir = self.app_service_fsplugin_inputdirManage(str_inputdir)

        str_exec = os.path.join(plugin.selfpath, plugin.selfexec)
        l_appArgs = [str(s) for s in app_args]  # convert all arguments to string
        str_allCmdLineArgs = ' '.join(l_appArgs)
        str_cmd = '%s %s' % (str_exec, str_allCmdLineArgs)
        logger.info('cmd = %s', str_cmd)
        #logger.debug('inputdir = %s', str_inputdir)

        str_outputdir = self.c_plugin_inst.get_output_path()
        # logger.debug('outputdir = %s', str_outputdir)

        d_pluginInst = vars(self.c_plugin_inst)
        # logger.debug('d_pluginInst = %s', d_pluginInst)

        str_serviceName = self.str_jid_prefix + str(d_pluginInst['id'])
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
                    'cmd': "%s %s" % (self.c_plugin_inst.plugin.execshell, str_cmd),
                    'threaded': True,
                    'auid': self.c_plugin_inst.owner.username,
                    'jid': str_serviceName,
                    'number_of_workers': str(d_pluginInst['number_of_workers']),
                    'cpu_limit': str(d_pluginInst['cpu_limit']),
                    'memory_limit': str(d_pluginInst['memory_limit']),
                    'gpu_limit': d_pluginInst['gpu_limit'],
                    "container":
                        {
                            "target":
                                {
                                    "image": self.c_plugin_inst.plugin.dock_image,
                                    "cmdParse": False,
                                    "selfexec": self.c_plugin_inst.plugin.selfexec,
                                    "selfpath": self.c_plugin_inst.plugin.selfpath,
                                    "execshell": self.c_plugin_inst.plugin.execshell
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
                                            "serviceName": str_serviceName
                                        }
                                }
                        },
                    "service": str_IOPhost
                }
        }
        self.app_service_call(d_msg)

    def check_plugin_instance_app_exec_status(self):
        """
        Check a plugin instance's app execution status. It connects to the remote
        service to determine job status and if just finished without error,
        register output files.
        """
        # pudb.set_trace()
        d_msg = {
            "action": "status",
            "meta": {
                    "remote": {
                        "key": self.str_jid_prefix + str(self.c_plugin_inst.id)
                    }
            }
        }
        d_responseStatus = self.responseStatus_decode(
            self.app_rawAndSummaryInfo_serialize(self.app_service_call(d_msg))
        )
        str_responseStatus = d_responseStatus['response']
        logger.info('Current job remote status = %s', str_responseStatus)

        d_response = d_responseStatus['d_serialize']['d_response']
        logger.info('d_response = %s', json.dumps(d_response, indent=4, sort_keys=True))

        if d_responseStatus['status']:
            str_DBstatus = self.c_plugin_inst.status
            logger.info('Current job DB status = %s', str_DBstatus)

            if 'swiftPut:True' in str_responseStatus and \
                    str_DBstatus != 'finishedSuccessfully':
                self.app_register_files(d_response, d_msg)

        # Some possible error handling...
        if str_responseStatus == 'finishedWithError':
            self.app_handleRemoteError()

    def cancel_plugin_instance_app_exec(self):
        """
        Cancel a plugin instance's app execution. It connects to the remote service
        to cancel job.
        """
        pass

    def app_service_call(self, d_msg):
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
        # speak to the service...
        d_response = json.loads(serviceCall())

        str_service = 'pfcon'
        if isinstance(d_response, dict):
            logger.info('looks like we got a successful response from %s', str_service)
            logger.info('comms were sent to -->%s<--', remote_url)
            logger.info('response from pfurl(): %s', json.dumps(d_response, indent=2))
        else:
            logger.info('looks like we got an UNSUCCESSFUL response from %s', str_service)
            logger.info('comms were sent to -->%s<--', remote_url)
            logger.info('response from pfurl(): -->%s<--', d_response)
        if "Connection refused" in d_response:
            logging.error('fatal error in talking to %s', str_service)
        return d_response

    def app_service_fsplugin_inputdirManage(self, inputdir):
        """
        This method is responsible for managing the 'inputdir' in the
        case of FS plugins.

        An FS plugin does not have an inputdir spec, since this is only a requirement
        for DS plugins. Nonetheless, the underlying management system (pfcon/pfurl) does
        require some non-zero inputdir spec in order to operate correctly.

        The hack here is to store data somewhere in swift and accessing it as a
        "pseudo" inputdir for FS plugins. For example, if an FS plugin has no arguments
        of type 'path', then we create a "dummy" inputdir with a small dummy text file
        in swift storage. This is then transmitted as an 'inputdir' to the compute
        environment, and can be completely ignored by the plugin.

        Importantly, one major exception to the normal FS processing scheme
        exists: an FS plugin that collects data from object storage. This
        storage location is not an 'inputdir' in the traditional sense, and is
        thus specified in the FS plugin argument list as argument of type
        'path' (i.e. there is no positional argument for inputdir as in DS
        plugins. Thus, if a type 'path' argument is specified, this 'path'
        is assumed to denote a location in object storage.

        In the case when a 'path' type argument is specified, there
        are certain important caveats:

            1. Only one 'path' type argument is assumed / fully supported.
            2. If an invalid object location is specified, this is squashed.

        (squashed means that the system will still execute, but the returned
        output directory from the FS plugin will contain only a single file
        with the text 'squash' in its filename and the file will contain
        some descriptive message)
        """
        # Remove any leading noise on the inputdir
        str_inputdir = inputdir.strip().lstrip('.')
        homedir = os.path.expanduser("~")
        if str_inputdir:
            # Check if dir spec exists in swift
            try:
                path_exists = self.swift_manager.path_exists(str_inputdir)
            except Exception as e:
                logger.error('Swift storage error, detail: %s' % str(e))
                return str_inputdir
            if path_exists:
                return str_inputdir
            str_squashFile = os.path.join(homedir,
                                          'data/squashInvalidDir/squashInvalidDir.txt')
            str_squashMsg = 'Path specified in object storage does not exist!'
        else:
            # No parameter of type 'path' was submitted, so input dir is empty
            str_squashFile = os.path.join(homedir,
                                          'data/squashEmptyDir/squashEmptyDir.txt')
            str_squashMsg = 'Empty input dir.'

        # Check if squash file already exists in object storage
        try:
            obj_exists = self.swift_manager.obj_exists(str_squashFile)
        except Exception as e:
            logger.error('Swift storage error, detail: %s' % str(e))
            return str_inputdir
        if obj_exists:
            # Here the file was found, so 'objPath' is a file spec.
            # We need to prune this into a path spec...
            str_inputdir = os.path.dirname(str_squashFile)
        else:
            # Create a squash file in Swift storage with descriptive message...
            with io.StringIO(str_squashMsg) as f:
                try:
                    self.swift_manager.upload_file(str_squashFile, f.read(),
                                                   content_type='text/plain')
                except Exception as e:
                    logger.error('Swift storage error, detail: %s' % str(e))
                else:
                    str_inputdir = os.path.dirname(str_squashFile)
        return str_inputdir

    def app_register_files(self, d_response, d_msg):
        """
        Method to register files received from the remote process into CUBE.
        """
        b_swiftFound = False
        d_swiftState = {}
        if 'swiftPut' in d_response['jobOperation']['info']:
            d_swiftState = d_response['jobOperation']['info']['swiftPut']
            b_swiftFound = True
        maxPolls = 10
        currentPoll = 1
        while not b_swiftFound and currentPoll <= maxPolls:
            if 'swiftPut' in d_response['jobOperation']['info']:
                d_swiftState = d_response['jobOperation']['info']['swiftPut']
                logger.info('Found swift return data on poll %d', currentPoll)
                break
            logger.info('swift return data not found on poll %d; sleeping...',
                        currentPoll)
            time.sleep(0.2)
            d_response = self.app_service_call(d_msg)
            currentPoll += 1
        d_register = self.c_plugin_inst.register_output_files(swiftState=d_swiftState)

        str_responseStatus = 'finishedSuccessfully'
        self.c_plugin_inst.status = str_responseStatus
        logger.info("Saving job DB status   as '%s'", self.c_plugin_inst.status)

        self.c_plugin_inst.end_date = timezone.now()
        logger.info("Saving job DB end_date as '%s'", self.c_plugin_inst.end_date)

        self.c_plugin_inst.save()
        return d_register

    def app_rawAndSummaryInfo_serialize(self, d_response):
        """
        Serialize and save the 'jobOperation' and 'jobOperationSummary'
        """
        str_summary = json.dumps(d_response['jobOperationSummary'])
        str_raw = self.json_zipToStr(d_response['jobOperation'])
        # Still WIP about what is best summary...
        # a couple of options / ideas linger
        try:
            str_containerLogs = d_response['jobOperation'] \
                ['info'] \
                ['compute'] \
                ['return'] \
                ['d_ret'] \
                ['l_logs'][0]
        except:
            str_containerLogs = "Container logs not currently available."
        #logger.debug("str_summary = '%s'", str_summary)
        self.c_plugin_inst.summary = str_summary
        self.c_plugin_inst.raw = str_raw
        self.c_plugin_inst.save()

        return {
            'status': True,
            'raw': str_raw,
            'summary': str_summary,
            'd_response': d_response
        }

    def app_handleRemoteError(self):
        """
        Collect the 'stderr' from the remote app
        """
        str_deepVal = ''
        def str_deepnest(d):
            nonlocal str_deepVal
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
                "value": self.str_jid_prefix + str(self.c_plugin_inst.id),
                "job": "0",
                "when": "end",
                "field": "stderr"
            }
        }
        d_response = self.app_service_call(d_msg)
        str_deepnest(d_response['d_ret'])
        logger.error('deepVal = %s', str_deepVal)

        d_msg['meta']['field'] = 'returncode'
        d_response = self.app_service_call(d_msg)
        str_deepnest(d_response['d_ret'])
        logger.error('deepVal = %s', str_deepVal)

    @staticmethod
    def responseStatus_decode(d_serialize):
        """
        Based on the information in d_response['jobOperationSummary']
        determine and return a single string decoding.
        """
        str_responseStatus  = ""
        b_status            = False
        if d_serialize['status']:
            b_status        = True
            for str_action in ['pushPath', 'compute', 'pullPath', 'swiftPut']:
                if str_action == 'compute':
                    for str_part in ['submit', 'return']:
                        str_actionStatus    = str(d_serialize['d_response']\
                                                            ['jobOperationSummary']\
                                                            [str_action]\
                                                            [str_part]\
                                                            ['status'])
                        str_actionStatus    = ''.join(str_actionStatus.split())
                        str_responseStatus += str_action + '.' + str_part + ':' +\
                                                str_actionStatus + ';'
                else:
                    str_actionStatus        = str(d_serialize['d_response']\
                                                            ['jobOperationSummary']\
                                                            [str_action]\
                                                            ['status'])
                    str_actionStatus        = ''.join(str_actionStatus.split())
                    str_responseStatus     += str_action + ':' + str_actionStatus + ';'
        return {
            'status':       b_status,
            'response':     str_responseStatus,
            'd_serialize':  d_serialize
        }

    @staticmethod
    def json_zipToStr(json_data):
        """
        Return a string of compressed JSON data, suitable for transmission
        back to a client.
        """
        str_compressed = base64.b64encode(
            zlib.compress(
                json.dumps(json_data).encode('utf-8')
            )
        ).decode('ascii')

        return str_compressed
