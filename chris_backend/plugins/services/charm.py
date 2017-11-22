"""

charm - ChRIS / pfcon interface.

"""

import  os
import  pprint
import  datetime
import  json
import  pudb
import  pfurl
import  inspect
import  pfmisc

from django.conf import settings


class Charm():

    def log(self, *args):
        """
        get/set the log object.

        Caller can further manipulate the log object with object-specific
        calls.
        """
        if len(args):
            self._log = args[0]
        else:
            return self._log

    def name(self, *args):
        """
        get/set the descriptive name text of this object.
        """
        if len(args):
            self.__name = args[0]
        else:
            return self.__name

    def qprint(self, msg, **kwargs):

        str_teeFile = ''
        str_teeMode = 'w+'

        str_comms  = "status"
        for k,v in kwargs.items():
            if k == 'comms'     :   str_comms   = v
            if k == 'teeFile'   :   str_teeFile = v
            if k == 'teeMode'   :   str_teeMode = v  

        if self.b_useDebug:
            write   = self.debug
        else:
            write   = print

        if len(str_teeFile):
            tf      = open(str_teeFile, str_teeMode)

        # pudb.set_trace()

        str_caller  = inspect.stack()[1][3]

        str_print   = ''
        if not self.b_quiet:
            if not self.b_useDebug:
                if str_comms == 'status':   write(pfurl.Colors.PURPLE,    end="")
                if str_comms == 'error':    write(pfurl.Colors.RED,       end="")
                if str_comms == "tx":       write(pfurl.Colors.YELLOW + "---->")
                if str_comms == "rx":       write(pfurl.Colors.GREEN  + "<----")
                str_print = '%s' % datetime.datetime.now() + " "
                write(str_print,       end="")
            str_print += ' | ' + self.__name__ + "." + str_caller + '() | ' + msg
            write(str_print)
            if not self.b_useDebug:
                if str_comms == "tx":       write(pfurl.Colors.YELLOW + "---->")
                if str_comms == "rx":       write(pfurl.Colors.GREEN  + "<----")
                write(pfurl.Colors.NO_COLOUR, end="")
            if len(str_teeFile):
                tf.write(str_print)
                tf.close()

    def col2_print(self, str_left, str_right):
        print(pfurl.Colors.WHITE +
              ('%*s' % (self.LC, str_left)), end='')
        print(pfurl.Colors.LIGHT_BLUE +
              ('%*s' % (self.RC, str_right)) + pfurl.Colors.NO_COLOUR)

    def __init__(self, **kwargs):
        # threading.Thread.__init__(self)

        self._log                   = pfurl.Message()
        self._log._b_syslog         = True
        self.__name__               = "Charm"
        self.b_useDebug             = settings.CHRIS_DEBUG['useDebug']

        str_debugDir                = '%s/tmp' % os.environ['HOME']
        if not os.path.exists(str_debugDir):
            os.makedirs(str_debugDir)
        self.str_debugFile          = '%s/debug-charm.log' % str_debugDir

        if len(settings.CHRIS_DEBUG['debugFile']):
            self.str_debugFile      = settings.CHRIS_DEBUG['debugFile']

        self.str_http               = ""
        self.str_ip                 = ""
        self.str_port               = ""
        self.str_URL                = ""
        self.str_verb               = ""
        self.str_msg                = ""
        self.d_msg                  = {}
        self.str_protocol           = "http"

        self.dp                         = pfmisc.debug(    
                                            verbosity   = 0,
                                            level       = -1,
                                            within      = self.__name__ 
                                            )

        self.pp                     = pprint.PrettyPrinter(indent=4)
        self.b_man                  = False
        self.str_man                = ''
        self.b_quiet                = settings.CHRIS_DEBUG['quiet']
        self.b_raw                  = False
        self.auth                   = ''
        self.str_jsonwrapper        = ''

        self.str_IOPhost            = ''

        self.str_cmd                = ''
        self.str_inputdir           = ''
        self.str_outputdir          = ''
        self.d_args                 = {}
        self.l_appArgs              = {}
        self.c_pluginInst           = {'contents':  'void'}
        self.d_pluginRepr           = {}
        self.app                    = None

        self.LC                     = 40
        self.RC                     = 40

        for key, val in kwargs.items():
            if key == 'app_args':       self.l_appArgs      = val
            if key == 'd_args':         self.d_args         = val
            if key == 'plugin_inst':    self.c_pluginInst   = val
            if key == 'plugin_repr':    self.d_pluginRepr   = val
            if key == 'app':            self.app            = val
            if key == 'inputdir':       self.str_inputdir   = val
            if key == 'outputdir':      self.str_outputdir  = val
            if key == 'useDebug':       self.b_useDebug     = val
            if key == 'debugFile':      self.str_debugFile  = val
            if key == 'quiet':          self.b_quiet        = val
            if key == 'IOPhost':        self.str_IOPhost    = val

        if self.b_useDebug:
            self.debug                  = pfurl.Message(logTo = self.str_debugFile)
            self.debug._b_syslog        = True
            self.debug._b_flushNewLine  = True

        # This for the case when Charm is instantiated w/o a plugin instance, eg
        # as a dispatcher to simply send a pfcon instance a message.
        try:
            self.d_pluginInst   = vars(self.c_pluginInst)
        except:
            self.d_pluginInst   = {}

        # pudb.set_trace()

        if not self.b_quiet:
            print(pfurl.Colors.LIGHT_GREEN)
            print("""
            \t\t\t+---------------------+
            \t\t\t|  Welcome to charm!  |
            \t\t\t+---------------------+
            """)
            print(pfurl.Colors.CYAN + """
            'charm' is the interface class/code between ChRIS and a remote 
            REST-type server, typically 'pfcon'.

            """)
            if self.b_useDebug:
                print("""
            Debugging output is directed to the file '%s'.
                """ % (self.str_debugFile))
            else:
                print("""
            Debugging output will appear in *this* console.
                """)

        self.dp.qprint('d_args         = %s'   % self.pp.pformat(self.d_args).strip())
        self.dp.qprint('app_args       = %s'   % self.l_appArgs)
        self.dp.qprint('d_pluginInst   = %s'   % self.pp.pformat(self.d_pluginInst).strip())
        self.dp.qprint('d_pluginRepr   = %s'   % self.pp.pformat(self.d_pluginRepr).strip())
        self.dp.qprint('app            = %s'   % self.app)
        self.dp.qprint('inputdir       = %s'   % self.str_inputdir)
        self.dp.qprint('outputdir      = %s'   % self.str_outputdir)

    def app_manage(self, **kwargs):
        """
        Main "manager"/"dispatcher" for running plugins.
        """
        str_method  = 'internal'
        str_IOPhost = 'localhost'
        b_launched  = False

        for k,v in kwargs.items():
            if k == 'method':   str_method  = v
            if k == 'IOPhost':  str_IOPhost = v

        if str_method == 'internal':
            self.app_launchInternal()
            b_launched  = True
        if str_method == 'crunner':
            self.app_crunner()
            b_launched  = True
        if str_method == 'pfcon':
            self.app_service(   service = str_method,
                                IOPhost = str_IOPhost)

        if b_launched: self.c_pluginInst.register_output_files()

    def app_launchInternal(self):
        self.app.launch(self.l_appArgs)
        self.c_pluginInst.register_output_files()

    def app_crunnerWrap(self):
        """
        Run the "app" in a crunner instance.

        :param self:
        :return:
        """

        str_cmdLineArgs = ''.join('{} {}'.format(key, val) for key,val in sorted(self.d_args.items()))
        self.dp.qprint('cmdLindArgs = %s' % str_cmdLineArgs)

        str_allCmdLineArgs      = ' '.join(self.l_appArgs)
        str_exec                = os.path.join(self.d_pluginRepr['selfpath'], self.d_pluginRepr['selfexec'])

        if len(self.d_pluginRepr['execshell']):
            str_exec            = '%s %s' % (self.d_pluginRepr['execshell'], str_exec)

        self.str_cmd            = '%s %s' % (str_exec, str_allCmdLineArgs)
        self.dp.qprint('cmd = %s' % self.str_cmd)

        self.app_crunner(self.str_cmd, loopctl = True)
        self.c_pluginInst.register_output_files()

    def app_crunner(self, str_cmd, **kwargs):
        """
        Run the "app" in a crunner instance.

        :param self:
        :return:
        """

        # The loopctl controls whether or not to block on the
        # crunner shell job
        b_loopctl               = False

        for k,v in kwargs.items():
            if k == 'loopctl':  b_loopctl = v

        verbosity               = 1
        shell                   = pfurl.crunner(
                                            verbosity   = verbosity,
                                            debug       = True,
                                            debugTo     = '%s/tmp/debug-crunner.log' % os.environ['HOME'])

        shell.b_splitCompound   = True
        shell.b_showStdOut      = True
        shell.b_showStdErr      = True
        shell.b_echoCmd         = False

        shell(str_cmd)
        if b_loopctl:
            shell.jobs_loopctl()

    def app_service_shutdown(self, **kwargs):
        """
        This method sends a shutdown command over HTTP to a server process.

        :return:
        """

        # pudb.set_trace()

        str_service     = 'pfcon'

        for k,v in kwargs.items():
            if k == 'service':  str_service = v

        d_msg = {
            "action": "quit",
            "meta": {
                    "when":         "now",
                    "saveDB":       True
                }
        }
        d_response = self.app_service_call(msg = d_msg, service = str_service)

    def app_service_call(self, *args, **kwargs):
        """
        This method sends the JSON 'msg' argument to the remote service.

        :param args:
        :param kwargs:
        :return: True | False
        """

        d_msg                   = {}
        str_service             = 'pfcon'
        b_httpResponseBodyParse = True

        for k,v in kwargs.items():
            if k == 'msg':      d_msg       = v
            if k == 'service':  str_service = v

        # pudb.set_trace()

        str_setting     = 'settings.%s' % str_service.upper()
        str_http        = '%s:%s' % (eval(str_setting)['host'], 
                                     eval(str_setting)['port'])
        if str_service == 'pfcon': b_httpResponseBodyParse = False

        str_debugFile       = '%s/tmp/debug-pfurl.log' % os.environ['HOME']
        if self.str_debugFile == '/dev/null':
            str_debugFile   = self.str_debugFile

        serviceCall = pfurl.Pfurl(
            msg                     = json.dumps(d_msg),
            http                    = str_http,
            verb                    = 'POST',
            # contentType             = 'application/json',
            b_raw                   = True,
            b_quiet                 = self.b_quiet,
            b_httpResponseBodyParse = b_httpResponseBodyParse,
            jsonwrapper             = 'payload',
            debugFile               = str_debugFile,
            useDebug                = self.b_useDebug
        )

        # speak to the service...
        d_response      = json.loads(serviceCall())
        return d_response

    def app_service_checkIfAvailable(self, *args, **kwargs):
        """
        This method checks if the remote service is available by asking
        it for system status.

        :param args:
        :param kwargs:
        :return: True | False
        """

        # pudb.set_trace()
        return True
        # str_service     = 'pfcon'
        # str_IOPhost     = 'localhost'
        #
        # for k,v in kwargs.items():
        #     if k == 'service':  str_service = v
        #     if k == 'IOPhost':  str_IOPhost = v
        #
        # d_msg = {
        #     "action":   "hello",
        #     "meta": {
        #                 "askAbout":     "sysinfo",
        #                 "echoBack":     "All's well.",
        #                 "service":      str_IOPhost
        #     }
        # }
        #
        # self.dp.qprint('service type: %s' % str_service)
        # str_dmsg = self.pp.pformat(d_msg).strip()
        # if os.path.exists('/data'):
        #     if not os.path.exists('/data/tmp'):
        #         os.makedirs('/data/tmp')
        #     self.dp.qprint(str_dmsg, teeFile = '/data/tmp/dmsg-hello.json', teeMode = 'w+')
        # else:
        #     self.dp.qprint(str_dmsg, teeFile = '/tmp/dmsg-hello.json', teeMode = 'w+')
        # d_response = self.app_service_call(msg = d_msg, **kwargs)
        #
        # if isinstance(d_response, dict):
        #     self.dp.qprint('successful response from serviceCall(): %s ' % json.dumps(d_response, indent=2))
        #     ret = True
        # else:
        #     self.dp.qprint('unsuccessful response from serviceCall(): %s' % d_response)
        #     if "Connection refused" in d_response:
        #         pass
        #         # self.app_service_startup()
        #     ret = False
        # return ret

    def app_service_fsplugin_inputdirManage(self, *args, **kwargs):
        """
        NB: HACK ALERT! Relies on volume mapping meta info!

        This method creates a "fake" inputdir for fsplugins that is used
        by the file transfer service.
        """

        if os.path.isdir('/data'):
            if not os.path.exists('/data/dummy'):
                os.makedirs('/data/dummy')
            os.chdir('/data/dummy')
            # touch a file
            with open('dummy.txt', 'a'):
                os.utime('dummy.txt', None)
            os.chdir('../')
            self.str_inputdir   = os.path.abspath('dummy')
        else:
            self.str_inputdir   = '/etc'

    def app_service_fsplugin_setup(self, *args, **kwargs):
        """
        Some fsplugins, esp those that might interact with the local file
        filesystem can be "massaged" to conform to the existing fileIO 
        transmission pattern.

        This method edits the cmdLine for fsplugin input to /share/incoming 
        and sets any --dir to data localSource.
        """

        if 'dir' in self.d_args:
            self.str_inputdir = self.d_args['dir']
            i = 0
            for v in self.l_appArgs:
                if v == self.str_inputdir:
                    self.l_appArgs[i] = '/share/incoming'
                i+=1
            str_allCmdLineArgs      = ' '.join(self.l_appArgs)
            str_exec                = os.path.join(self.d_pluginRepr['selfpath'], self.d_pluginRepr['selfexec'])
            self.str_cmd            = '%s %s' % (str_exec, str_allCmdLineArgs)                 
            self.dp.qprint('cmd = %s' % self.str_cmd)
        if self.str_inputdir == './' or self.str_inputdir == '':
            self.app_service_fsplugin_inputdirManage()

        return {
            'status':   True,
            'cmd':      self.str_cmd,
            'inputdir': self.str_inputdir
        }

    def app_service(self, *args, **kwargs):
        """
        Run the "app" via a call to a service provider.
        """

        str_service     = 'pfcon'
        str_IOPhost     = 'localhost'

        for k,v in kwargs.items():
            if k == 'service':  str_service = v
            if k == 'IOPhost':  str_IOPhost = v

        # pudb.set_trace()
        
        # First, check if the remote service is available... 
        self.app_service_checkIfAvailable(**kwargs)

        self.dp.qprint('d_args = %s' % self.d_args)
        str_cmdLineArgs = ''.join('{} {} '.format(key, val) for key,val in sorted(self.d_args.items()))
        self.dp.qprint('cmdLineArg = %s' % str_cmdLineArgs)

        self.dp.qprint('l_appArgs = %s' % self.l_appArgs)
        str_allCmdLineArgs      = ' '.join(self.l_appArgs)
        str_exec                = os.path.join(self.d_pluginRepr['selfpath'], self.d_pluginRepr['selfexec'])

        # if len(self.d_pluginRepr['execshell']):
        #     str_exec            = '%s %s' % (self.d_pluginRepr['execshell'], str_exec)

        self.str_cmd            = '%s %s' % (str_exec, str_allCmdLineArgs)
        self.dp.qprint('cmd = %s' % self.str_cmd)

        if str_service == 'pfcon':
            # Handle the case for 'fs'-type plugins that don't specify an 
            # inputdir.
            #
            # Passing an empty string through to pfurl will cause it to fail 
            # on its local directory check.
            #
            # The "hack" here is to set the 'inputdir' to the fs plugin to the
            # 'dir' argument of its input CLI, if such an argument exists; 
            # otherwise, set to '/etc'. 
            #
            # Also, for 'fs' plugins, we need to set the "incoming" directory 
            # to /share/incoming.
            # pudb.set_trace()
            if self.str_inputdir == '':
                d_fs    = self.app_service_fsplugin_setup()
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
                        "path":         self.str_inputdir
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
                            "encoding": "none",
                            "archive":  "zip",
                            "unpack":   True,
                            "cleanup":  True
                        }
                    },
                    "service":              str_IOPhost
                },

                "meta-compute":  
                {
                    'cmd':      "$execshell " + self.str_cmd,
                    'threaded': True,
                    'auid':     self.c_pluginInst.owner.username,
                    'jid':      str(self.d_pluginInst['id']),
                    "container":   
                    {
                        "target": 
                        {
                            "image":            self.c_pluginInst.plugin.dock_image,
                            "cmdParse":         True
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
                                "serviceName":  str(self.d_pluginInst['id'])
                            }
                        }
                    },
                    "service":              str_IOPhost
                }
            }
            str_dmsg = self.pp.pformat(d_msg).strip()
            # pudb.set_trace()
            if os.path.exists('/data'):
                if not os.path.exists('/data/tmp'):
                    os.makedirs('/data/tmp')
                self.dp.qprint(str_dmsg, teeFile = '/data/tmp/dmsg-exec.json', teeMode = 'w+')
            else:
                self.dp.qprint(str_dmsg, teeFile = '/tmp/dmsg-exec.json', teeMode = 'w+')

        d_response  = self.app_service_call(msg = d_msg, **kwargs)

        if isinstance(d_response, dict):
            self.dp.qprint("looks like we got a successful response from %s" % str_service)
            self.dp.qprint('response from pfurl(): %s ' % json.dumps(d_response, indent=2))
        else:
            self.dp.qprint("looks like we got an UNSUCCESSFUL response from %s" % str_service)
            self.dp.qprint('response from pfurl(): %s' % d_response)
            if "Connection refused" in d_response:
                self.dp.qprint('fatal error in talking to %s' % str_service, comms = 'error')

    def app_statusCheckAndRegister(self, *args, **kwargs):
        """
        Check on the status of the job, and if just finished without error,
        register output files.
        """

        # pudb.set_trace()

        # Now ask the remote service for the job status
        d_msg   = {
            "action": "status",
            "meta": {
                    "remote": {
                        "key":       str(self.d_pluginInst['id'])
                    }
            }
        }

        d_response  = self.app_service_call(msg = d_msg, service = 'pfcon', **kwargs)
        self.dp.qprint('d_response = %s' % d_response)
        try:
            str_responseStatus  = d_response['jobOperationSummary']['compute']['return']['l_status'][0]
        except:
            str_responseStatus  = 'Error in response. No record of job found.'
        str_DBstatus    = self.c_pluginInst.status
        self.dp.qprint('Current job DB     status = %s' % str_DBstatus,          comms = 'status')
        self.dp.qprint('Current job remote status = %s' % str_responseStatus,    comms = 'status')
        if 'finished' in str_responseStatus and str_responseStatus != str_DBstatus:
            self.dp.qprint('Registering output files...', comms = 'status')
            registeredFiles             = self.c_pluginInst.register_output_files()
            self.c_pluginInst.status    = str_responseStatus
            self.c_pluginInst.end_date  = datetime.datetime.now()
            self.dp.qprint('Registered %d files...' % registeredFiles)
            self.c_pluginInst.save()
            self.dp.qprint("Saving job DB status   as '%s'" %  str_responseStatus,
                                                            comms = 'status')
            self.dp.qprint("Saving job DB end_date as '%s'" %  self.c_pluginInst.end_date,
                                                            comms = 'status')
        if str_responseStatus == 'finishedWithError': self.app_handleRemoteError(**kwargs)

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
                    # str_deepVal = v

        # Collect the 'stderr' from the app service for this instance
        d_msg   = {
            "action": "search",
            "meta": {
                "key":      "jid",
                "value":    str(self.d_pluginInst['id']),
                "job":      "0",
                "when":     "end",
                "field":    "stderr"
            }
        }
        d_response      = self.app_service_call(msg = d_msg, **kwargs)
        self.str_deep   = ''
        str_deepnest(d_response['d_ret'])
        self.dp.qprint(str_deepVal, comms = 'error')

        d_msg['meta']['field'] = 'returncode'
        d_response      = self.app_service_call(msg = d_msg, **kwargs)
        str_deepnest(d_response['d_ret'])
        self.dp.qprint(str_deepVal, comms = 'error')
