'''
/**
 *
 *            sSSs   .S    S.    .S_sSSs     .S    sSSs
 *           d%%SP  .SS    SS.  .SS~YS%%b   .SS   d%%SP
 *          d%S'    S%S    S%S  S%S   `S%b  S%S  d%S'
 *          S%S     S%S    S%S  S%S    S%S  S%S  S%|
 *          S&S     S%S SSSS%S  S%S    d* S  S&S  S&S
 *          S&S     S&S  SSS&S  S&S   .S* S  S&S  Y&Ss
 *          S&S     S&S    S&S  S&S_sdSSS   S&S  `S&&S
 *          S&S     S&S    S&S  S&S~YSY%b   S&S    `S*S
 *          S*b     S*S    S*S  S*S   `S%b  S*S     l*S
 *          S*S.    S*S    S*S  S*S    S%S  S*S    .S*P
 *           SSSbs  S*S    S*S  S*S    S&S  S*S  sSS*S
 *            YSSP  SSS    S*S  S*S    SSS  S*S  YSS'
 *                         SP   SP          SP
 *                         Y    Y           Y
 *
 *                       U  L  T  R  O  N 
 *
 * (c) 2016 Fetal-Neonatal Neuroimaging & Developmental Science Center
 *                   Boston Children's Hospital
 *
 *              http://childrenshospital.org/FNNDSC/
 *                        dev@babyMRI.org
 *
 */
'''
import os, sys
from argparse import ArgumentParser
import json

if "DJANGO_SETTINGS_MODULE" not in os.environ:
    # django needs to be loaded (eg. when some chris app is run from the command line)
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django
    django.setup()


class BaseClassAttrEnforcer(type):
    def __init__(cls, name, bases, d):
        # class variables to be enforced in the subclasses
        attrs = ['DESCRIPTION', 'TYPE', 'TITLE', 'LICENSE']
        for attr in attrs:
            if attr not in d:
                raise ValueError("Class %s doesn't define %s class variable" % (name,
                                                                                attr))
        type.__init__(cls, name, bases, d)
        

class ChrisApp(ArgumentParser, metaclass=BaseClassAttrEnforcer):
    '''
    The super class for all valid ChRIS plugin apps.
    '''
    
    AUTHORS = 'FNNDSC (dev@babyMRI.org)'
    TITLE = ''
    CATEGORY = ''
    TYPE = 'ds'
    DESCRIPTION = None
    DOCUMENTATION = ''
    LICENSE = ''
    VERSION = ''
  
    def __init__(self):
        '''
        The constructor of this app.
        '''
        super(ChrisApp, self).__init__(description=self.DESCRIPTION)
        self.options = []
        # the custom parameter list
        self._parameters = []
        self.add_argument('--json', action='store_true', dest='json', default=False,
                           help='show json representation of app (default: FALSE)')
        self.add_argument('--description', action='store_true', dest='description',
                           default=False,
                           help='show the description of this plugin (default: FALSE)')
        if self.TYPE=='ds':
            # 'ds' plugins require an input directory
            self.add_argument('inputdir', action='store', type=str,
                              help='directory containing the input files')
        # all plugins require an output directory
        self.add_argument('outputdir', action='store', type=str,
                              help='directory containing the output files/folders')
        self.add_argument('--opts', action='store', dest='opts',
                          help='file containing the arguments passed to this app')
        self.add_argument('--saveopts', action='store', dest='saveopts', default=False,
                           help='save arguments to a JSON file (default: FALSE)')
        self.define_parameters()

    def define_parameters(self):
        '''
        Define the parameters used by this app (abstract method in this class). 
        '''
        raise NotImplementedError("ChrisApp.define_parameters(self)")

    def run(self, options):
        '''
        Execute this app (abstract method in this class). 
        '''
        raise NotImplementedError("ChrisApp.run(self, options)")

    def add_parameter(self, *args, **kwargs):
        '''
        Add a parameter to this app. 
        '''
        # make sure required parameter options were defined
        try:
            name = kwargs['dest']
            param_type = kwargs['type']
            optional = kwargs['optional']
            action = kwargs['action']
        except KeyError as e:
            detail = "%s option required. " % e 
            raise KeyError(detail)
        if optional and ('default' not in kwargs):
            detail = "A default values is required for optional parameter %s." % name
            raise KeyError(detail)

        # grab the default and help values
        default = None
        if 'default' in kwargs:
            default = kwargs['default']
        param_help = ""
        if 'help' in kwargs:
            param_help = kwargs['help']

        # store the parameters internally    
        param = {'name': name, 'type': param_type, 'optional': optional, 'flag': args[0],
                 'action': action, 'help': param_help, 'default': default}
        self._parameters.append(param)

        # add the parameter to the parser
        del kwargs['optional']
        self.add_argument(*args, **kwargs)

    def get_json_representation(self):
        '''
        Return a JSON object with a representation of this app (type and parameters).
        '''
        repres                  = {}
        repres['type']          = self.TYPE
        repres['parameters']    = self._parameters
        repres['selfpath']      = self.SELFPATH
        repres['selfexec']      = self.SELFEXEC
        return repres

    def launch(self, args=None):
        '''
        This method triggers the parsing of arguments. The run() method gets called 
        if not --json or --description are specified.
        '''
        options = self.parse_args(args)
        if (options.json):
            print(self.get_json_representation())
        elif (options.description):
            print(self.DESCRIPTION)
        elif (options.opts):
             # run the app with options read from JSON file
            self.run(self.get_options_from_file(options.opts))
        else:
            if (options.saveopts):
                self.save_options(options, options.saveopts)
            # run the app
            self.run(options)

    def get_options_from_file(self, file_path):
        '''
        Return the options parsed from a JSON file. 
        '''
        #read options JSON file
        options_dict = {}
        with open(file_path) as options_file:    
            options_dict = json.load(options_file)
        options = []
        for opt_name in options_dict:
            options.append(opt_name)
            options.append(options_dict[opt_name])        
        return self.parse_args(options)

    def save_options(self, options, file_path):
        '''
        Save the options passed to the app to a JSON file. 
        '''
        with open(file_path, 'w') as outfile:
            json.dump(vars(options), outfile)

    def error(self, message):
        '''
        The error handler if wrong commandline arguments are specified.
        '''
        print()
        sys.stderr.write('ERROR: %s\n' % message)
        print()
        self.print_help()
        sys.exit(2)

