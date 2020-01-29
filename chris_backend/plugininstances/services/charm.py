"""

charm - ChRIS / pfcon interface.

"""

import  os
from os.path import expanduser
import  pprint
import  json
import  pudb
import  pfurl
import  pfmisc

from    urllib.parse    import  parse_qs
from    django.utils    import  timezone
from    django.conf     import  settings

from    pfmisc._colors  import  Colors
from    pfmisc.message  import  Message

import  swiftclient
import  time

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

    def verbosity(self, *args):
        """
        get/set the descriptive name text of this object.
        """
        if len(args):
            self.dp.verbosity = args[0]
        else:
            return self.dp.verbosity

    def col2_print(self, str_left, str_right, level = 1):
        self.dp.qprint(Colors.WHITE +
              ('%*s' % (self.LC, str_left)), 
              end       = '',
              level     = level,
              syslog    = False)
        self.dp.qprint(Colors.LIGHT_BLUE +
              ('%*s' % (self.RC, str_right)) + Colors.NO_COLOUR,
              level     = level,
              syslog    = False
              )

    def __init__(self, **kwargs):
        # threading.Thread.__init__(self)

        self._log                   = Message()
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

        self.dp                     = pfmisc.debug(    
                                            verbosity   = 1,
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
        self.app                    = None

        self.LC                     = 40
        self.RC                     = 40

        # A job ID prefix string. Necessary since some schedulers require
        # a minimum job ID string length
        self.str_jidPrefix          = 'chris-jid-'

        for key, val in kwargs.items():
            if key == 'app_args':       self.l_appArgs         = val
            if key == 'd_args':         self.d_args            = val
            if key == 'plugin_inst':    self.c_pluginInst      = val
            if key == 'app':            self.app               = val
            if key == 'inputdir':       self.str_inputdir      = val
            if key == 'outputdir':      self.str_outputdir     = val
            if key == 'useDebug':       self.b_useDebug        = val
            if key == 'debugFile':      self.str_debugFile     = val
            if key == 'quiet':          self.b_quiet           = val
            if key == 'IOPhost':        self.str_IOPhost       = val

        if self.b_useDebug:
            self.debug                  = Message(logTo = self.str_debugFile)
            self.debug._b_syslog        = True
            self.debug._b_flushNewLine  = True

        if self.b_quiet:
            self.dp.verbosity = -10

        # This for the case when Charm is instantiated w/o a plugin instance, eg
        # as a dispatcher to simply send a pfcon instance a message.
        try:
            self.d_pluginInst   = vars(self.c_pluginInst)
        except:
            self.d_pluginInst   = {}

        # pudb.set_trace()

        if not self.b_quiet:
            str_desc = Colors.CYAN + """
                                +---------------------+
                                |  Welcome to charm!  |
                                +---------------------+
            """ + Colors.LIGHT_GREEN + """

            'charm' is the interface class/code between ChRIS and a remote 
            REST-type server, typically 'pfcon'.

            This module is the only contact boundary between ChRIS and 
            external/remote services.

            Debugging output is currently sent to """ + Colors.YELLOW
            if self.b_useDebug:
                str_desc += "'" + self.str_debugFile +"'"
            else:
                str_desc += "*this* console"
            str_desc += Colors.NO_COLOUR

            self.dp.qprint(str_desc)

        self.dp.qprint('d_args         = %s'   % self.pp.pformat(self.d_args).strip())
        self.dp.qprint('app_args       = %s'   % self.l_appArgs)
        self.dp.qprint('d_pluginInst   = %s'   % self.pp.pformat(self.d_pluginInst).strip())
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

    # def app_crunnerWrap(self):
    #     """
    #     Run the "app" in a crunner instance.

    #     :param self:
    #     :return:
    #     """

    #     str_cmdLineArgs = ''.join('{} {}'.format(key, val) for key,val in sorted(self.d_args.items()))
    #     self.dp.qprint('cmdLindArgs = %s' % str_cmdLineArgs)

    #     str_allCmdLineArgs      = ' '.join(self.l_appArgs)
    #     str_exec                = os.path.join(self.c_pluginInst.plugin.selfpath, self.c_pluginInst.plugin.selfexec)

    #     if len(self.c_pluginInst.plugin.execshell):
    #         str_exec            = '%s %s' % (self.c_pluginInst.plugin.execshell, str_exec)

    #     self.str_cmd            = '%s %s' % (str_exec, str_allCmdLineArgs)
    #     self.dp.qprint('cmd = %s' % self.str_cmd)

    #     self.app_crunner(self.str_cmd, loopctl = True)
    #     self.c_pluginInst.register_output_files()

    # def app_crunner(self, str_cmd, **kwargs):
    #     """
    #     Run the "app" in a crunner instance.

    #     :param self:
    #     :return:
    #     """

    #     # The loopctl controls whether or not to block on the
    #     # crunner shell job
    #     b_loopctl               = False

    #     for k,v in kwargs.items():
    #         if k == 'loopctl':  b_loopctl = v

    #     verbosity               = 1
    #     shell                   = pfurl.crunner(
    #                                         verbosity   = verbosity,
    #                                         debug       = True,
    #                                         debugTo     = '%s/tmp/debug-crunner.log' % os.environ['HOME'])

    #     shell.b_splitCompound   = True
    #     shell.b_showStdOut      = True
    #     shell.b_showStdErr      = True
    #     shell.b_echoCmd         = False

    #     shell(str_cmd)
    #     if b_loopctl:
    #         shell.jobs_loopctl()

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
        if str_service == 'pman': b_httpResponseBodyParse = False

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
        if not b_httpResponseBodyParse:
            d_response  = parse_qs(d_response)
        return d_response

    def app_service_checkIfAvailable(self, *args, **kwargs):
        """
        This method checks if the remote service is available by asking
        it for system status.

        It is currently deprecated.

        :param args:
        :param kwargs:
        :return: True | False
        """
        return True


    def swiftstorage_connect(self, *args, **kwargs):
        """
        Connect to swift storage and return the connection object,
        as well an optional "prepend" string to fully qualify 
        object location in swift storage.
        """

        b_status                = True
        b_prependBucketPath     = False

        for k,v in kwargs.items():
            if k == 'prependBucketPath':    b_prependBucketPath = v

        d_ret       = {
            'status':               b_status,
            'conn':                 None,
            'prependBucketPath':    ""
        }

        # initiate a swift service connection, based on internal
        # settings already available in the django variable space.
        try:
            d_ret['conn'] = swiftclient.Connection(
                user    = settings.SWIFT_USERNAME,
                key     = settings.SWIFT_KEY,
                authurl = settings.SWIFT_AUTH_URL,
            )
        except:
            d_ret['status'] = False

        if b_prependBucketPath:
            # d_ret['prependBucketPath']  = self.c_pluginInst.owner.username + '/uploads'
	    # The following line should "root" requests to swift storage to the user
	    # space and allow for access/dircopy to the feed space and not only 
	    # the 'uploads' space.
            # d_ret['prependBucketPath']  = self.c_pluginInst.owner.username
            d_ret['prependBucketPath']  = ''

        return d_ret

    def swiftstorage_ls(self, *args, **kwargs):
        """
        Return a list of objects in the swiftstorage
        """
        l_ls                    = []    # The listing of names to return
        ld_obj                  = {}    # List of dictionary objects in swift
        str_path                = '/'
        str_fullPath            = ''
        b_prependBucketPath     = False
        b_status                = False

        for k,v in kwargs.items():
            if k == 'path':                 str_path            = v
            if k == 'prependBucketPath':    b_prependBucketPath = v

        # Remove any leading noise on the str_path, specifically
        # any leading '.' characters.
        # This is probably not very robust!
        while str_path[:1] == '.':  str_path    = str_path[1:]

        d_conn          = self.swiftstorage_connect(**kwargs)
        if d_conn['status']:
            conn        = d_conn['conn']
            if b_prependBucketPath:
                str_fullPath    = '%s%s' % (d_conn['prependBucketPath'], str_path)
            else:
                str_fullPath    = str_path

            # get the full list of objects in Swift storage with given prefix
            ld_obj = conn.get_container( settings.SWIFT_CONTAINER_NAME, 
                                        prefix          = str_fullPath,
                                        full_listing    = True)[1]        

            for d_obj in ld_obj:
                l_ls.append(d_obj['name'])
                b_status    = True
        
        return {
            'status':       b_status,
            'objectDict':   ld_obj,
            'lsList':       l_ls,
            'fullPath':     str_fullPath
        }

    def swiftstorage_objExists(self, *args, **kwargs):
        """
        Return True/False if passed object exists in swift storage
        """        
        b_exists    = False
        str_obj     = ''

        for k,v in kwargs.items():
            if k == 'obj':                  str_obj             = v
            if k == 'prependBucketPath':    b_prependBucketPath = v

        kwargs['path']  = str_obj
        d_swift_ls  = self.swiftstorage_ls(*args, **kwargs)
        str_obj     = d_swift_ls['fullPath']

        if d_swift_ls['status']:
            for obj in d_swift_ls['lsList']:
                if str_obj in obj:
                    b_exists = True

        return {
            'status':   b_exists,
            'objPath':  str_obj
        }

    def swiftstorage_objPut(self, *args, **kwargs):
        """
        Put an object (or list of objects) into swift storage.

        By default, to location in storage will map 1:1 to the
        location name string in the local filesytem. This storage
        location can be remapped by using the '<toLocation>' and
        '<mapLocationOver>' kwargs. For example, assume
        a list of local locations starting with:

                /home/user/project/data/ ...

        and we want to pack everything in the 'data' dir to 
        object storage, at location '/storage'. In this case, the
        pattern of kwargs specifying this would be:

                    fileList = ['/home/user/project/data/file1',
                                '/home/user/project/data/dir1/file_d1',
                                '/home/user/project/data/dir2/file_d2'],
                    toLocation      = '/storage',
                    mapLocationOver = '/home/user/project/data'

        will replace, for each file in <fileList>, the <mapLocationOver> with
        <toLocation>, resulting in a new list

                    '/storage/file1', 
                    '/storage/dir1/file_d1',
                    '/storage/dir2/file_d2'

        Note that the <toLocation> is subject to <b_prependBucketPath>!

        """
        b_status                = True
        l_localfile             = []    # Name on the local file system
        l_objectfile            = []    # Name in the object storage
        str_swiftLocation       = ''
        str_mapLocationOver     = ''
        str_localfilename       = ''
        str_storagefilename     = ''
        str_prependBucketPath   = ''
        d_ret                   = {
            'status':           b_status,
            'localFileList':    [],
            'objectFileList':   []
        }

        d_conn  = self.swiftstorage_connect(*args, **kwargs)
        if d_conn['status']:
            str_prependBucketPath       = d_conn['prependBucketPath']

        str_swiftLocation               = str_prependBucketPath

        for k,v in kwargs.items():
            if k == 'file':             l_localfile.append(v)
            if k == 'fileList':         l_localfile         = v
            if k == 'toLocation':       str_swiftLocation   = '%s%s' % (str_prependBucketPath, v)
            if k == 'mapLocationOver':  str_mapLocationOver = v

        if len(str_mapLocationOver):
            # replace the local file path with object store path
            l_objectfile    = [w.replace(str_mapLocationOver, str_swiftLocation) \
                                for w in l_localfile]
        else:
            # Prepend the swiftlocation to each element in the localfile list:
            l_objectfile    = [str_swiftLocation + '{0}'.format(i) for i in l_localfile]

        if d_conn['status']:
            for str_localfilename, str_storagefilename in zip(l_localfile, l_objectfile): 
                try:
                    d_ret['status'] = True and d_ret['status']
                    with open(str_localfilename, 'r') as fp:
                        d_conn['conn'].put_object(
                            settings.SWIFT_CONTAINER_NAME,
                            str_storagefilename,
                            contents=fp.read()
                        )
                except:
                    d_ret['status'] = False
                d_ret['localFileList'].append(str_localfilename)
                d_ret['objectFileList'].append(str_storagefilename)
        return d_ret

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
        squashdir = os.path.join(expanduser("~"), 'data/squash')
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
        d_ret['d_objExists'] = self.swiftstorage_objExists(
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
                d_ret['d_objPut']       = self.swiftstorage_objPut(
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
        homedir = expanduser("~")
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
        d_objExists     = self.swiftstorage_objExists(
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
                self.dp.qprint('cmd = %s' % self.str_cmd)

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
        self.l_appArgs = [str(s) for s in self.l_appArgs] # convert all arguments to string
        str_allCmdLineArgs      = ' '.join(self.l_appArgs)
        str_exec                = os.path.join(self.c_pluginInst.plugin.selfpath, self.c_pluginInst.plugin.selfexec)

        # if len(self.c_pluginInst.plugin.execshell):
        #     str_exec            = '%s %s' % (self.c_pluginInst.plugin.execshell, str_exec)

        self.str_cmd            = '%s %s' % (str_exec, str_allCmdLineArgs)
        self.dp.qprint('cmd = %s' % self.str_cmd)
        if str_service == 'pfcon':
            # Handle the case for 'fs'-type plugins that don't specify an 
            # inputdir, in which case the self.str_inputdir is empty.
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
            datadir = os.path.join(expanduser("~"), 'data')
            if os.path.exists(datadir):
                if not os.path.exists(os.path.join(datadir, 'tmp')):
                    os.makedirs(os.path.join(datadir, 'tmp'))
                self.dp.qprint( str_pfurlCmdExec, 
                                teeFile = os.path.join(datadir, 'tmp/dmsg-exec-%s.json' % str_serviceName),
                                teeMode = 'w+')
                self.dp.qprint( str_pfurlCmdStatus, 
                                teeFile = os.path.join(datadir, 'tmp/dmsg-stat-%s.json' % str_serviceName),
                                teeMode = 'w+')
            else:
                self.dp.qprint( str_pfurlCmdExec, 
                                teeFile = '/tmp/dmsg-exec-%s.json' % str_serviceName, 
                                teeMode = 'w+')
                self.dp.qprint( str_pfurlCmdStatus, 
                                teeFile = '/tmp/dmsg-stat-%s.json' % str_serviceName, 
                                teeMode = 'w+')

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
                        "key":       self.str_jidPrefix + str(self.d_pluginInst['id'])
                    }
            }
        }

        d_response  = self.app_service_call(msg = d_msg, service = 'pfcon', **kwargs)
        self.dp.qprint('d_response = %s' % json.dumps(d_response, indent = 4, sort_keys = True))
        str_responseStatus  = ""
        for str_action in ['pushPath', 'compute', 'pullPath', 'swiftPut']:
            if str_action == 'compute':
                for str_part in ['submit', 'return']:
                    str_actionStatus = str(d_response['jobOperationSummary'][str_action][str_part]['status'])
                    str_actionStatus = ''.join(str_actionStatus.split())
                    str_responseStatus += str_action + '.' + str_part + ':' + str_actionStatus + ';'
            else:
                str_actionStatus = str(d_response['jobOperationSummary'][str_action]['status'])
                str_actionStatus = ''.join(str_actionStatus.split())
                str_responseStatus += str_action + ':' + str_actionStatus + ';'

        str_DBstatus    = self.c_pluginInst.status
        self.dp.qprint('Current job DB     status = %s' % str_DBstatus,          comms = 'status')
        self.dp.qprint('Current job remote status = %s' % str_responseStatus,    comms = 'status')
        if 'swiftPut:True' in str_responseStatus and str_DBstatus != 'finishedSuccessfully':
            # pudb.set_trace()
            b_swiftFound    = False
            d_swiftState    = {}
            if 'swiftPut' in d_response['jobOperation']['info']:
                d_swiftState    = d_response['jobOperation']['info']['swiftPut']
                b_swiftFound    = True
            maxPolls        = 10
            currentPoll     = 1
            while not b_swiftFound and currentPoll <= maxPolls: 
                if 'swiftPut' in d_response['jobOperation']['info']:
                    d_swiftState    = d_response['jobOperation']['info']['swiftPut']
                    b_swiftFound    = True
                    self.dp.qprint('Found swift return data on poll %d' % currentPoll)
                    break
                self.dp.qprint('swift return data not found on poll %d; will sleep a bit...' % currentPoll)
                time.sleep(0.2)
                d_response  = self.app_service_call(msg = d_msg, service = 'pfcon', **kwargs)
                currentPoll += 1

            d_register      = self.c_pluginInst.register_output_files(
                                                swiftState = d_swiftState
            )

            # This doesn't work when CUBE container is not started as root
            # str_registrationMsg = """
            # Registering output files...
            #
            # pfcon swift poll loops      = %d
            # charm swift poll loops      = %d
            # swift prefix path           = %s
            #
            # In total, registered %d objects.
            #
            # Object list:\n""" % (
            #         d_register['pollLoop'],
            #         currentPoll,
            #         d_register['outputPath'],
            #         d_register['total']
            # )
            # #pudb.set_trace()
            # for obj in d_register['l_object']:
            #     str_registrationMsg += obj['name'] + '\n'
            # self.dp.qprint('%s' % str_registrationMsg, status = 'comms',
            #                 teeFile = 'os.path.join(expanduser("~"), 'data/tmp/registrationMsg-%s.txt' %  str(self.d_pluginInst['id'])),
            #                 teeMode = 'w+')


            str_responseStatus          = 'finishedSuccessfully'
            self.c_pluginInst.status    = str_responseStatus
            self.c_pluginInst.end_date  = timezone.now()
            self.c_pluginInst.save()
            self.dp.qprint("Saving job DB status   as '%s'" %  str_responseStatus,
                                                            comms = 'status')
            self.dp.qprint("Saving job DB end_date as '%s'" %  self.c_pluginInst.end_date,
                                                            comms = 'status')

        # NB: Improve error handling!!
        if str_responseStatus == 'finishedWithError': self.app_handleRemoteError(**kwargs)
        return str_responseStatus

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
                "value":    self.str_jidPrefix + str(self.d_pluginInst['id']),
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
