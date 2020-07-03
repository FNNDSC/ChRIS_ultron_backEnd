"""

charm - ChRIS / pfcon interface.

"""

import logging
import os
import time
import json
from urllib.parse import parse_qs
import zlib, base64

from django.utils import timezone
from django.conf import settings

import pfurl

from .swiftmanager import SwiftManager

if settings.DEBUG:
    import pdb
    import pudb
    from celery.contrib import rdb


logger = logging.getLogger(__name__)


class Charm():

    def __init__(self, **kwargs):
        # threading.Thread.__init__(self)

        self.__name__               = "Charm"
        self.str_http               = ""
        self.d_msg                  = {}
        self.b_raw                  = False
        self.str_IOPhost            = ''
        self.str_cmd                = ''
        self.str_inputdir           = ''
        self.str_outputdir          = ''
        self.d_args                 = {}
        self.l_appArgs              = {}
        self.c_pluginInst           = {'contents':  'void'}
        self.app                    = None

        # A job ID prefix string. Necessary since some schedulers require
        # a minimum job ID string length
        self.str_jidPrefix = 'chris-jid-'

        for key, val in kwargs.items():
            if key == 'app_args':       self.l_appArgs         = val
            if key == 'd_args':         self.d_args            = val
            if key == 'plugin_inst':    self.c_pluginInst      = val
            if key == 'app':            self.app               = val
            if key == 'inputdir':       self.str_inputdir      = val
            if key == 'outputdir':      self.str_outputdir     = val
            if key == 'IOPhost':        self.str_IOPhost       = val

        # This for the case when Charm is instantiated w/o a plugin instance, eg
        # as a dispatcher to simply send a pfcon instance a message.
        try:
            self.d_pluginInst = vars(self.c_pluginInst)
        except:
            self.d_pluginInst = {}

        # pudb.set_trace()

        # logger.debug('d_args = %s', self.d_args)
        # logger.debug('app_args = %s', self.l_appArgs)
        # logger.debug('d_pluginInst = %s', self.d_pluginInst)
        # logger.debug('app = %s', self.app)
        # logger.debug('inputdir = %s', self.str_inputdir)
        # logger.debug('outputdir = %s', self.str_outputdir)

    def app_manage(self, **kwargs):
        """
        Main "manager"/"dispatcher" for running plugins.
        """
        str_method = 'internal'
        str_IOPhost = 'localhost'

        for k,v in kwargs.items():
            if k == 'method':   str_method = v
            if k == 'IOPhost':  str_IOPhost = v

        if str_method == 'internal':
            self.app_launchInternal()
        if str_method == 'pfcon':
            self.app_service(service=str_method, IOPhost=str_IOPhost)

    def app_launchInternal(self):
        """
        Run the "app" directly in this process.
        """
        self.app.launch(self.l_appArgs)
        self.c_pluginInst.register_output_files()

    def app_service(self, *args, **kwargs):
        """
        Run the "app" via a call to a remote service provider.
        """
        str_service     = 'pfcon'
        str_IOPhost     = 'localhost'

        for k,v in kwargs.items():
            if k == 'service':  str_service = v
            if k == 'IOPhost':  str_IOPhost = v

        # pudb.set_trace()

        # logger.debug('d_args = %s', self.d_args)
        # logger.debug('cmdLineArg = %s', str_cmdLineArgs)
        # logger.debug('l_appArgs = %s', self.l_appArgs)
        self.l_appArgs = [str(s) for s in self.l_appArgs] # convert all arguments to string
        str_allCmdLineArgs      = ' '.join(self.l_appArgs)
        str_exec                = os.path.join(self.c_pluginInst.plugin.selfpath, self.c_pluginInst.plugin.selfexec)
        self.str_cmd            = '%s %s' % (str_exec, str_allCmdLineArgs)
        logger.info('cmd = %s', self.str_cmd)

        if str_service == 'pfcon':
            # Handle the case for 'fs'-type plugins that don't specify an
            # inputdir, in which case the self.str_inputdir is empty.
            #
            # Passing an empty string through to pfurl will cause it to fail
            # on its local directory check.
            #
            # The "hack" here is to check on the inputdir strings. In the case
            # of FS-type plugins this is '' or an empty string. Note this is
            # NOT Null!
            #
            # In such a case, charm will "transparently" set the input dir to
            # a location in swift
            #
            #       /home/localuser/data/squashInvalidDir
            #
            # which in turn contains a "file"
            #
            #       /home/localuser/data/squashInvalidDir/squashInvalidDir.txt
            #
            # This "inputdir" is then sent along with `pfcon/pfurl` and is of
            # course ignored by the actual plugin when it is run. This does have
            # the anti-pattern side effect of possibly using this to send
            # completely OOB (out of band) data to an FS plugin in this "fake"
            # "inputdir" and could have implications. Right now though I don't
            # see how an FS plugin could even access this fake "inputdir".
            #
            # pudb.set_trace()

            if self.str_inputdir == '':
                d_fs    = self.app_service_fsplugin_setup()
                self.str_inputdir   = d_fs['d_manage']['d_handle']['inputdir']
            str_serviceName = self.str_jidPrefix + str(self.d_pluginInst['id'])
            d_msg = \
            {
                "action": "coordinate",
                "threadAction":   True,
                "meta-store":
                {
                        "meta":         "meta-compute",
                        "key":          "jid"
                },

                "meta-data":
                {
                    "remote":
                    {
                        "key":          "%meta-store"
                    },
                    "localSource":
                    {
                        "path":         self.str_inputdir,
                        "storageType":  "swift"
                    },
                    "localTarget":
                    {
                        "path":         self.str_outputdir,
                        "createDir":    True
                    },
                    "specialHandling":
                    {
                        "op":           "plugin",
                        "cleanup":      True
                    },
                    "transport":
                    {
                        "mechanism":    "compress",
                        "compress":
                        {
                            "archive":  "zip",
                            "unpack":   True,
                            "cleanup":  True
                        }
                    },
                    "service":              str_IOPhost
                },

                "meta-compute":
                {
                    'cmd':               "%s %s" % (self.c_pluginInst.plugin.execshell, self.str_cmd),
                    'threaded':          True,
                    'auid':              self.c_pluginInst.owner.username,
                    'jid':               str_serviceName,
                    'number_of_workers': str(self.d_pluginInst['number_of_workers']),
                    'cpu_limit':         str(self.d_pluginInst['cpu_limit']),
                    'memory_limit':      str(self.d_pluginInst['memory_limit']),
                    'gpu_limit':         self.d_pluginInst['gpu_limit'],
                    "container":
                    {
                        "target":
                        {
                            "image":            self.c_pluginInst.plugin.dock_image,
                            "cmdParse":         False,
                            "selfexec":         self.c_pluginInst.plugin.selfexec,
                            "selfpath":         self.c_pluginInst.plugin.selfpath,
                            "execshell":        self.c_pluginInst.plugin.execshell
                        },
                        "manager":
                        {
                            "image":            "fnndsc/swarm",
                            "app":              "swarm.py",
                            "env":
                            {
                                "meta-store":   "key",
                                "serviceType":  "docker",
                                "shareDir":     "%shareDir",
                                "serviceName":  str_serviceName
                            }
                        }
                    },
                    "service":              str_IOPhost
                }
            }
            d_status   = {
                    "action": "status",
                    "meta": {
                            "remote": {
                                "key":       str_serviceName
                            }
                    }
                }
            str_dmsgExec = json.dumps(d_msg,    indent = 4, sort_keys = True)
            str_dmsgStat = json.dumps(d_status, indent = 4, sort_keys = True)

            str_pfurlCmdHeader = """\npfurl \\
                    --verb POST --raw --http ${HOST_IP}:5005/api/v1/cmd \\
                    --httpResponseBodyParse                             \\
                    --jsonwrapper 'payload' --msg '"""
            str_pfurlCmdExec    = str_pfurlCmdHeader + """
            %s
            '
            """ % str_dmsgExec
            str_pfurlCmdStatus = str_pfurlCmdHeader + """
            %s
            '
            """ % str_dmsgStat

            ###
            # NB: This is a good break point in charm to pause
            #     execution and not keep interrupting downstream
            #     service for status data that might break debugging
            #     context in services like 'pfcon'
            #
            #     Simply comment/uncomment the break point and "Next"
            #     along to the self.app_service_call
            ##
            ## pudb.set_trace()

            logger.info('pfurlCmdExec = %s', str_pfurlCmdExec)
            logger.info('pfurlCmdStatus = %s', str_pfurlCmdStatus)

        d_response = self.app_service_call(d_msg)

        if isinstance(d_response, dict):
            logger.info('looks like we got a successful response from %s', str_service)
            logger.info('response from pfurl(): %s', json.dumps(d_response, indent=2))
        else:
            logger.info('looks like we got an UNSUCCESSFUL response from %s', str_service)
            logger.info('response from pfurl(): %s', d_response)
            if "Connection refused" in d_response:
                logging.error('fatal error in talking to %s', str_service)

    def app_service_call(self, d_msg):
        """
        This method sends the JSON 'msg' argument to the remote service.
        """
        b_httpResponseBodyParse = True

        # pudb.set_trace()
        str_http = settings.PFCON_URL

        serviceCall = pfurl.Pfurl(
            msg                     = json.dumps(d_msg),
            http                    = str_http,
            verb                    = 'POST',
            # contentType             = 'application/json',
            b_raw                   = True,
            b_quiet                 = True,
            b_httpResponseBodyParse = b_httpResponseBodyParse,
            jsonwrapper             = 'payload',
        )
        # speak to the service...
        d_response = json.loads(serviceCall())
        if not b_httpResponseBodyParse:
            d_response = parse_qs(d_response)
        return d_response

    def app_service_fsplugin_squashFileHandle(self, *args, **kwargs):
        """
        This method is used under certain conditions:

            * An FS plugin has specified an "illegal" directory in
              the object store:
                    * /     root of store
                    * ./    relative "current" dir

            * An FS plugin has specified a non-existent directory/file
              in the object store.

        In each case, this method creates an appropriately named "dummy"
        file in the object store and specifies its parent directory as
        the directory to pull from the store.

        The effect is that if an FS plugin specifies one of these "illegal"
        conditions, a file is created in the FS plugin output that contains
        this somewhat descriptive filename.

        This method appends the correct username for swift purposes to
        the 'inputdir'.

        **kwargs:
            squashFilePath
            squashFileMessage
        """
        b_status                = False
        squashdir = os.path.join(os.path.expanduser("~"), 'data/squash')
        str_squashFilePath      = os.path.join(squashdir, 'unspecifiedSquashFile.txt')
        str_squashFileMessage   = 'Unspecified message.'
        d_ret                   = {
            'status':               b_status,
            'b_squashFileFound':    False,
            'inputdir':             '',
            'd_objPut':             {},
            'd_objExists':          {}
        }

        for k,v in kwargs.items():
            if k == 'squashFilePath':       str_squashFilePath      = v
            if k == 'squashFileMessage':    str_squashFileMessage   = v

        str_squashParentPath, str_squashFile = os.path.split(str_squashFilePath)

        # Check if squash file exists in object storage
        d_ret['d_objExists'] = SwiftManager.objExists(
                                        obj                 = str_squashFilePath,
                                        prependBucketPath   = True
                                )
        d_ret['b_squashFileFound']  = d_ret['d_objExists']['status']

        # If not, create and push...
        if not d_ret['b_squashFileFound']:
            # Create a squash file...
            try:
                if not os.path.exists(str_squashParentPath):
                    os.makedirs(str_squashParentPath)
                os.chdir(str_squashParentPath)
                # Create a squashfile with possibly descriptive message
                with open(str_squashFile, 'w') as f:
                    print(str_squashFileMessage, file=f)
                # and push to swift...
                d_ret['d_objPut']       = SwiftManager.objPut(
                                            file                = str_squashFilePath,
                                            prependBucketPath   = True
                                        )
                str_swiftLocation       = d_ret['d_objPut']['objectFileList'][0]
                d_ret['inputdir']       = os.path.dirname(str_swiftLocation)
                d_ret['status']         = True
            except:
                d_ret['status']         = False
        else:
            # Here the file was found, so 'objPath' is a file spec.
            # We need to prune this into a path spec...
            d_ret['status']     = True
            d_ret['inputdir']   = os.path.dirname(
                                        d_ret['d_objExists']['objPath']
                                    )
        return d_ret

    def app_service_fsplugin_inputdirManage(self, *args, **kwargs):
        """
        This method is responsible for managing the 'inputdir' in the
        case of FS plugins.

        Typically, an FS plugin does not have an inputdir spec, since this
        is a requirement for DS plugins. Nonetheless, the underlying management
        system (pfcon/pfurl) does require some non-zero inputdir spec in order
        to operate correctly.

        However, this operational requirement allows us a convenient
        mechanism to inject data into an FS processing stream by storing
        data in swift and accessing this as a "pseudo" inputdir for FS
        plugins.

        For example, if an FS plugin has no arguments of type 'path', then
        we create a "dummy" inputdir with a small dummy text file in swift
        storage. This is then transmitted as an 'inputdir' to the compute
        environment, and can be completely ignored by the plugin.

        Importantly, one major exception to the normal FS processing scheme
        exists: an FS plugin that collects data from object storage. This
        storage location is not an 'inputdir' in the traditional sense, and is
        thus specified in the FS plugin argument list as argument of type
        'path' (i.e. there is no positional argument for inputdir as in DS
        plugins. Thus, if a type 'path' argument is specified, this 'path'
        is assumed to denote a location in object storage.

        In the case then that a 'path' type argument is specified, there
        are certain important caveats:

            1. Only one 'path' type argument is assumed / fully supported.
            2. Open ended (or relative) path arguments are not supported
               (otherwise an entire object storage tree could be exposed):
                * directory specifcations of '/' are not supported and
                  are squashed;
                * directory specification of './' are not supported and
                  are squashed;
            3. If an invalid object location is specified, this is squashed.

        (squashed means that the system will still execute, but the returned
        output directory from the FS plugin will contain only a single file
        with the text 'squash' in its filename and the file will contain
        some descriptive message)
        """
        b_status            = False
        str_inputdir        = ''
        d_ret               = {
            'status':       b_status,
            'd_handle':     {}
        }

        for k,v in kwargs.items():
            if k == 'inputdir': str_inputdir    = v

        # First, check and return on illegal dir specs
        homedir = os.path.expanduser("~")
        if str_inputdir == '/' or str_inputdir == './':
            if str_inputdir == '/':
                str_squashFile  = os.path.join(homedir, 'data/squashRoot/squashRoot.txt')
                str_squashMsg   = 'Illegal dir spec, "/", passed to plugin.'
            if str_inputdir == './':
                str_squashFile  = os.path.join(homedir, 'data/squashHereDir/squashHereDir.txt')
                str_squashMsg   = 'Illegal dir spec, "./", passed to plugin.'
            d_ret['d_handle'] = self.app_service_fsplugin_squashFileHandle(
                squashFilePath      = str_squashFile,
                squashFileMessage   = str_squashMsg
            )
            d_ret['status'] = True
            return d_ret

        # Check if dir spec exists in swift
        d_objExists     = SwiftManager.objExists(
                            obj                 = str_inputdir,
                            prependBucketPath   = True
                        )
        b_pathValid     = d_objExists['status']
        if not b_pathValid:
            str_squashFile  = os.path.join(homedir, 'data/squashInvalidDir/squashInvalidDir.txt')
            str_squashMsg   = 'Path specified in object storage does not exist!'
            d_ret['d_handle'] = self.app_service_fsplugin_squashFileHandle(
                squashFilePath      = str_squashFile,
                squashFileMessage   = str_squashMsg
            )
            d_ret['status'] = True
            return d_ret
        else:
            d_ret['status'] = True
            d_ret['d_handle']['inputdir']  = d_objExists['objPath']
        return d_ret

    def app_service_fsplugin_setup(self, *args, **kwargs):
        """
        Some fsplugins, esp those that might interact with the local file
        filesystem can be "massaged" to conform to the existing fileIO
        transmission pattern.

        This method edits the cmdLine for fsplugin input to /share/incoming
        and sets any --dir to data location in local object storage.
        """
        # pudb.set_trace()
        l_pathArgs  = []

        # Loop over the plugin parameters and search for any that have type
        # 'path'. Ideally speaking there should be only one, however for now
        # we won't assume that -- we'll lay the groundwork for more than 'path'
        # type parameter, but will process things as if there was only one...
        for d_param in self.c_pluginInst.plugin.parameters.all():
            if d_param.type == 'path':
                l_pathArgs.append(d_param.name)

        # The 'path' type parameter refers to some location (ideally in the
        # swift storage). We need to replace this location referring to some
        # 'local' path with a hard code '/share/incoming' since that is where
        # the data will be located in the remote compute env.
        #
        # We then need to pass this local input parameter as the inputdir to
        # pfcon, with appropriate pre-massaging for bucket prepending.
        if len(l_pathArgs):
            for argName in l_pathArgs:
                self.str_inputdir = self.d_args[argName]
                i = 0
                for v in self.l_appArgs:
                    if v == self.str_inputdir:
                        self.l_appArgs[i] = '/share/incoming'
                    i+=1
                str_allCmdLineArgs      = ' '.join(self.l_appArgs)
                str_exec                = os.path.join(self.c_pluginInst.plugin.selfpath, self.c_pluginInst.plugin.selfexec)
                self.str_cmd            = '%s %s' % (str_exec, str_allCmdLineArgs)
                logger.info('cmd = %s', self.str_cmd)

        # Manage args with type 'path' for FS type plugins
        # At the point the 'self.str_inputdir' now points to the location
        # of the 'path' type variable in the arg list of the FS app.
        # We will pass this new location on to be managed via kwargs
        kwargs['inputdir']  = self.str_inputdir
        d_manage = self.app_service_fsplugin_inputdirManage(*args, **kwargs)

        return {
            'status':   True,
            'cmd':      self.str_cmd,
            'd_manage': d_manage
        }

    def app_statusCheckAndRegister(self, *args, **kwargs):
        """
        Check on the status of the job, and if just finished without error,
        register output files.

        NOTE:

            This is now part of an asynchronous celery worker. To debug
            synchronously with pudb.set_trace() you need to:

            1. Once CUBE is running, and assuming some plugininstance
               has been POSTed, start a python shell on the manage.py
               code (note <IMAGE> below is the chris:dev container):

                    docker exec -ti <IMAGE> python manage.py shell

                You should now be in a python shell.

            3. To simulate operations on a given plugin with id <id>,
               instantiate the relevant objects (for ex, for id=1):

                    from plugininstances.models import PluginInstance
                    from plugininstances.services import charm

                    plg_inst        = PluginInstance.objects.get(id=1)
                    chris_service   = charm.Charm(plugin_inst=plg_inst)

            4. And finally, call this method:

                    chris_service.app_statusCheckAndRegister()

                Any pudb.set_trace() calls in this method will now be
                handled by the pudb debugger.

            5. Finally, after each change to this method, reload this module:

                    import importlib

                    importlib.reload(charm)

                and also re-instantiate the service

                    chris_service   = charm.Charm(plugin_inst=plg_inst)
        """
        # pudb.set_trace()
        d_msg = {
            "action": "status",
            "meta": {
                    "remote": {
                        "key": self.str_jidPrefix + str(self.d_pluginInst['id'])
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
            str_DBstatus = self.c_pluginInst.status
            logger.info('Current job DB status = %s', str_DBstatus)

            if 'swiftPut:True' in str_responseStatus and \
                str_DBstatus != 'finishedSuccessfully':
                d_register = self.app_register_files(d_response, d_msg)

        self.c_pluginInst.save()

        # Some possible error handling...
        if str_responseStatus == 'finishedWithError':
            self.app_handleRemoteError(**kwargs)

        return str_responseStatus

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

        d_register = self.c_pluginInst.register_output_files(swiftState=d_swiftState)

        str_responseStatus = 'finishedSuccessfully'
        self.c_pluginInst.status = str_responseStatus
        self.c_pluginInst.end_date = timezone.now()

        logger.info("Saving job DB status   as '%s'", str_responseStatus)
        logger.info("Saving job DB end_date as '%s'", self.c_pluginInst.end_date)

        return d_register

    def app_rawAndSummaryInfo_serialize(self, d_response):
        """
        Serialize and save the 'jobOperation' and 'jobOperationSummary'
        """
        str_summary = json.dumps(d_response['jobOperationSummary'])
        # str_raw         = json.dumps(d_response['jobOperation'],
        #                             indent     = 4,
        #                             sort_keys  = True)
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
        # self.c_pluginInst.summary   = 'logs: %s' % str_containerLogs
        self.c_pluginInst.summary = str_summary
        self.c_pluginInst.raw = str_raw
        return {
            'status': True,
            'raw': str_raw,
            'summary': str_summary,
            'd_response': d_response
        }

    def app_handleRemoteError(self, *args, **kwargs):
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
        d_msg   = {
            "action": "search",
            "meta": {
                "key":      "jid",
                "value":    self.str_jidPrefix + str(self.d_pluginInst['id']),
                "job":      "0",
                "when":     "end",
                "field":    "stderr"
            }
        }
        d_response      = self.app_service_call(d_msg)
        self.str_deep   = ''
        str_deepnest(d_response['d_ret'])
        logger.error('deepVal = %s', str_deepVal)

        d_msg['meta']['field'] = 'returncode'
        d_response      = self.app_service_call(d_msg)
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
