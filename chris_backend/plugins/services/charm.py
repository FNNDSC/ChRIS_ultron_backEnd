#!/usr/bin/env python3.5

"""

charm - ChRIS / pman interface.

"""

from django.conf import settings

import  sys
import  os
import  pprint
import  datetime
import  socket
import  json
import  pudb

import  pman

# from    pman.pman           import pman
# from    pman._colors        import Colors
# from    pman.crunner        import crunner
# from    pman.purl           import Purl
# from    pman.message        import Message

# class pman_settings():
#
#     p           = pman.__path__
#     str_path    = '/' + str(p).split("'/")[1].split("']")[0]
#
#     HOST        =  [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
#     PORT        = '5010'
#     EXEC        = 'python3'
#     PATH        = '%s/pman.py' % str_path
#     ARGS        = "--raw 1 --http --port %s --listeners 12 --debugToFile --debugFile %s/tmp/debug-pman.log" % \
#                     ( PORT, os.environ['HOME'] )

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

        str_comms  = "status"
        for k,v in kwargs.items():
            if k == 'comms':    str_comms  = v

        if self.b_useDebug:
            write   = self.debug
        else:
            write   = print

        # pudb.set_trace()

        if not self.b_quiet:
            if not self.b_useDebug:
                if str_comms == 'status':   write(pman.Colors.PURPLE,    end="")
                if str_comms == 'error':    write(pman.Colors.RED,       end="")
                if str_comms == "tx":       write(pman.Colors.YELLOW + "---->")
                if str_comms == "rx":       write(pman.Colors.GREEN  + "<----")
                write('%s' % datetime.datetime.now() + " ",       end="")
            write(' | ' + msg)
            if not self.b_useDebug:
                if str_comms == "tx":       write(pman.Colors.YELLOW + "---->")
                if str_comms == "rx":       write(pman.Colors.GREEN  + "<----")
                write(pman.Colors.NO_COLOUR, end="")

    def col2_print(self, str_left, str_right):
        print(pman.Colors.WHITE +
              ('%*s' % (self.LC, str_left)), end='')
        print(pman.Colors.LIGHT_BLUE +
              ('%*s' % (self.RC, str_right)) + pman.Colors.NO_COLOUR)

    def __init__(self, **kwargs):
        # threading.Thread.__init__(self)

        self._log                   = pman.Message()
        self._log._b_syslog         = True
        self.__name                 = "Charm"
        self.b_useDebug             = False

        str_debugDir                = '%s/tmp' % os.environ['HOME']
        if not os.path.exists(str_debugDir):
            os.makedirs(str_debugDir)
        self.str_debugFile          = '%s/debug-charm.log' % str_debugDir

        self.str_http               = ""
        self.str_ip                 = ""
        self.str_port               = ""
        self.str_URL                = ""
        self.str_verb               = ""
        self.str_msg                = ""
        self.d_msg                  = {}
        self.str_protocol           = "http"
        self.pp                     = pprint.PrettyPrinter(indent=4)
        self.b_man                  = False
        self.str_man                = ''
        self.b_quiet                = False
        self.b_raw                  = False
        self.auth                   = ''
        self.str_jsonwrapper        = ''
        self.str_inputdir           = ''
        self.str_outputdir          = ''

        self.d_args                 = {}
        self.l_appArgs              = {}
        self.c_pluginInst           = {}
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

        if self.b_useDebug:
            self.debug                  = pman.Message(logTo = self.str_debugFile)
            self.debug._b_syslog        = True
            self.debug._b_flushNewLine  = True

        self.d_pluginInst   = vars(self.c_pluginInst)

        if not self.b_quiet:

            print(pman.Colors.LIGHT_GREEN)
            print("""
            \t\t\t+---------------------+
            \t\t\t|  Welcome to charm!  |
            \t\t\t+---------------------+
            """)
            print(pman.Colors.CYAN + """
            'charm' is the interface class/code between ChRIS and a pman process management
            system.

            Type 'charm.py --man commands' for more help. """)
            if self.b_useDebug:
                print("""
            Debugging output is directed to the file '%s'.
                """ % (self.str_debugFile))
            else:
                print("""
            Debugging output will appear in *this* console.
                """)

        self.qprint('d_args         = %s'   % self.pp.pformat(self.d_args).strip())
        self.qprint('app_args       = %s'   % self.l_appArgs)
        self.qprint('d_pluginInst   = %s'   % self.pp.pformat(self.d_pluginInst).strip())
        self.qprint('d_pluginRepr   = %s'   % self.pp.pformat(self.d_pluginRepr).strip())
        self.qprint('app            = %s'   % self.app)
        self.qprint('inputdir       = %s'   % self.str_inputdir)
        self.qprint('outputdir      = %s'   % self.str_outputdir)

    def app_manage(self, **kwargs):
        """
        Main "manager"/"dispatcher" for running plugins.
        """
        str_method  = 'internal'
        b_launched  = False
        for k,v in kwargs.items():
            if k == 'method':   str_method  = v

        if str_method == 'internal':
            self.app_launchInternal()
            b_launched  = True
        if str_method == 'crunner':
            self.app_crunner()
            b_launched  = True
        if str_method == 'pman':
            self.app_pman()

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
        self.qprint('cmdLindArgs = %s' % str_cmdLineArgs)

        str_allCmdLineArgs      = ' '.join(self.l_appArgs)
        str_exec                = os.path.join(self.d_pluginRepr['selfpath'], self.d_pluginRepr['selfexec'])

        if len(self.d_pluginRepr['execshell']):
            str_exec            = '%s %s' % (self.d_pluginRepr['execshell'], str_exec)

        str_cmd                 = '%s %s' % (str_exec, str_allCmdLineArgs)
        self.qprint('cmd = %s' % str_cmd)

        self.app_crunner(str_cmd, loopctl = True)
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
        shell                   = pman.crunner(verbosity = verbosity,
                                          debug     = True,
                                          debugTo   = '%s/tmp/debug-crunner.log' % os.environ['HOME'])

        shell.b_splitCompound   = True
        shell.b_showStdOut      = True
        shell.b_showStdErr      = True
        shell.b_echoCmd         = True

        shell(str_cmd)
        if b_loopctl:
            shell.jobs_loopctl()

    def app_pman_checkIfAvailable(self, *args, **kwargs):
        """
        This method checks if the remote 'pman' service is available by asking
        'pman' for system status.

        :param args:
        :param kwargs:
        :return: True | False
        """

        d_msg = {
            "action":   "hello",
            "meta": {
                        "askAbout":     "sysinfo",
                        "echoBack":     "Hi there!"
            }
        }

        # pudb.set_trace()

        str_http        = '%s:%s' % (settings.PMAN['host'], settings.PMAN['port'])

        purl    = pman.Purl(
            msg         = json.dumps(d_msg),
            http        = str_http,
            verb        = 'POST',
            contentType = 'application/vnd.collection+json',
            b_raw       = True,
            b_quiet     = False,
            jsonwrapper = 'payload',
            debugFile   = '%s/tmp/debug-purl.log' % os.environ['HOME'],
            useDebug    = self.b_useDebug
        )

        # speak to pman...
        d_response      = json.loads(purl())
        if isinstance(d_response, dict):
            self.qprint('successful response from purl() in checkIfAvailable: %s ' % json.dumps(d_response, indent=2))
        else:
            self.qprint('unsuccessful response from purl(): %s' % d_response)
            if "Connection refused" in d_response:
                self.app_pman_start()

    def app_pman(self, *args, **kwargs):
        """
        Run the "app" via pman
        """

        # The following snippet sets the pman IP to the actual host
        # Set the pman IP to specific host IP.
        # This is to address some issues on development relating to proxy handling.
        # If your setup complains at this line, simply comment it out and leave
        # the host as 'localhost'
        #settings.PMAN['host']   = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]

        str_http        = '%s:%s' % (settings.PMAN['host'], settings.PMAN['port'])

        # First, check if pman is available... and start it if it is not.
        self.app_pman_checkIfAvailable()

        self.qprint('d_args = %s' % self.d_args)
        str_cmdLineArgs = ''.join('{} {} '.format(key, val) for key,val in sorted(self.d_args.items()))
        self.qprint('in app_pman, cmdLineArg = %s' % str_cmdLineArgs)

        self.qprint('in app_pman, l_appArgs = %s' % self.l_appArgs)
        str_allCmdLineArgs      = ' '.join(self.l_appArgs)
        str_exec                = os.path.join(self.d_pluginRepr['selfpath'], self.d_pluginRepr['selfexec'])

        if len(self.d_pluginRepr['execshell']):
            str_exec            = '%s %s' % (self.d_pluginRepr['execshell'], str_exec)

        str_cmd                 = '%s %s' % (str_exec, str_allCmdLineArgs)
        self.qprint('in app_pman, cmd = %s' % str_cmd)

        d_msg = {
            'action':   'run',
            'meta': {
                        'cmd':      str_cmd,
                        'threaded': True,
                        'auid':     self.c_pluginInst.owner.username,
                        'jid':      str(self.d_pluginInst['id'])
            }
        }

        # pudb.set_trace()

        purl    = pman.Purl(
            msg         = json.dumps(d_msg),
            http        = str_http,
            verb        = 'POST',
            contentType = 'application/vnd.collection+json',
            b_raw       = True,
            b_quiet     = False,
            jsonwrapper = 'payload',
            debugFile   = '%s/tmp/debug-purl.log' % os.environ['HOME'],
            useDebug    = self.b_useDebug
        )

        # run the app
        d_response      = json.loads(purl())
        if isinstance(d_response, dict):
            self.qprint("looks like we got a successful response from pman")
            self.qprint('response from purl(): %s ' % json.dumps(d_response, indent=2))
        else:
            self.qprint("looks like we got an UNSUCCESSFUL response from pman")
            self.qprint('response from purl(): %s' % d_response)
            if "Connection refused" in d_response:
                self.qprint('in app pman, fatal error in talking to pman', comms = 'error')

    def app_pman_start(self, *args, **kwargs):
        """
        Attempt to start a remote pman service.

        This method is called is an attempt to speak with a pman service is unsuccessful, and
        the assumption is that 'pman' is down. We will attempt to start 'pman' for this
        user in this case.

        :param args:
        :param kwargs:
        :return:
        """
        self.qprint("It seems that 'pman' is not running... I will attempt to start it.\n\n")

        # str_pmanPath    = '/' + str(pman.__path__).split("'/")[1].split("']")[0] + '/pman.py'

        self.qprint('pman IP: %s' % settings.PMAN['host'])

        pmanArgs        = {
            'ip':           settings.PMAN['host'],
            'port':         settings.PMAN['port'],
            'raw':          '1',
            'protocol':     'tcp',
            'listeners':    '12',
            'http':         True,
            'debugToFile':  True,
            'debugFile':    '%s/tmp/debug-charm-internal.py' % os.environ['HOME']
        }

        self.qprint('Calling pman constructor internally.')
        self.qprint('pmanArgs = %s' % pmanArgs)

        print(pmanArgs)

        comm    = pman.pman(
            IP          = pmanArgs['ip'],
            port        = pmanArgs['port'],
            protocol    = pmanArgs['protocol'],
            raw         = pmanArgs['raw'],
            listeners   = pmanArgs['listeners'],
            http        = pmanArgs['http'],
            debugToFile = pmanArgs['debugToFile'],
            debugFile   = pmanArgs['debugFile']
        )
        comm.start()
        self.qprint('Called pman constructor internally.')

        #
        #     HOST        =  [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
        #     PORT        = '5010'
        #     EXEC        = 'python3'
        #     PATH        = '%s/pman.py' % str_path
        #     ARGS        = "--raw 1 --http --port %s --listeners 12 --debugToFile --debugFile %s/tmp/debug-pman.log" % \
        #                     ( PORT, os.environ['HOME'] )


        # str_pmanStart   = '%s %s %s' % (pman_settings.EXEC, pman_settings.PATH, pman_settings.ARGS)
        # self.qprint('pman start cmd = %s' % str_pmanStart)
        # pudb.set_trace()
        # self.app_crunner('%s' % str_pmanStart, loopctl = False)

    def app_statusCheckAndRegister(self, *args, **kwargs):
        """
        Check on the status of the job, and if just finished without error,
        register output files.
        """

        # First get current status
        str_status  = self.c_pluginInst.status

        # Now ask pman for the job status
        d_msg   = {
            "action": "status",
            "meta": {
                    "key":      "jid",
                    "value":    str(self.d_pluginInst['id'])
            }
        }
        str_http        = '%s:%s' % (settings.PMAN['host'], settings.PMAN['port'])

        purl    = pman.Purl(
            msg         = json.dumps(d_msg),
            http        = str_http,
            verb        = 'POST',
            contentType = 'application/vnd.collection+json',
            b_raw       = True,
            b_quiet     = False,
            jsonwrapper = 'payload',
            debugFile   = '%s/tmp/debug-purl.log' % os.environ['HOME'],
            useDebug    = self.b_useDebug
        )

        d_pman          = json.loads(purl())
        print( d_pman )
        str_pmanStatus  = d_pman['d_ret']['l_status'][0]
        str_DBstatus    = self.c_pluginInst.status
        self.qprint('Current job DB   status = %s' % str_DBstatus,          comms = 'status')
        self.qprint('Current job pman status = %s' % str_pmanStatus,        comms = 'status')
        if 'finished' in str_pmanStatus and str_pmanStatus != str_DBstatus:
            self.qprint('Registering output files...', comms = 'status')
            self.c_pluginInst.register_output_files()
            self.c_pluginInst.status    = str_pmanStatus
            self.c_pluginInst.end_date  = datetime.datetime.now()
            self.c_pluginInst.save()
            self.qprint("Saving job DB status   as '%s'" %  str_pmanStatus,
                                                            comms = 'status')
            self.qprint("Saving job DB end_date as '%s'" %  self.c_pluginInst.end_date,
                                                            comms = 'status')
        if str_pmanStatus == 'finishedWithError': self.app_handleRemoteError()


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

        # Collect the 'stderr' from pman for this instance
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
        str_http        = '%s:%s' % (settings.PMAN['host'], settings.PMAN['port'])

        purl    = pman.Purl(
            msg         = json.dumps(d_msg),
            http        = str_http,
            verb        = 'POST',
            contentType = 'application/vnd.collection+json',
            b_raw       = True,
            b_quiet     = False,
            jsonwrapper = 'payload',
            debugFile   = '%s/tmp/debug-purl.log' % os.environ['HOME'],
            useDebug    = self.b_useDebug
        )

        self.str_deep   = ''
        d_pman          = json.loads(purl())
        str_deepnest(d_pman['d_ret'])
        self.qprint(str_deepVal, comms = 'error')

        purl.d_msg['meta']['field'] = 'returncode'
        d_pman          = json.loads(purl())
        str_deepnest(d_pman['d_ret'])
        self.qprint(str_deepVal, comms = 'error')

if __name__ == '__main__':

    str_defIP = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
    str_defPort = 5010

    parser  = argparse.ArgumentParser(description = 'interface between ChRIS and pman')

    sys.exit(0)

