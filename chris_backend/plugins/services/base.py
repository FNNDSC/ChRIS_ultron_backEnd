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
import sys, os
import json
from argparse import ArgumentParser

class ChrisApp(ArgumentParser):
    '''
    The super class for all valid ChRIS apps.
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
        self.add_argument('--json', action='store_true', dest='json', default=False,
                           help='show json representation of app (default: FALSE)')
        self.add_argument('--description', action='store_true', dest='description',
                           default=False,
                           help='show the description of this plugin (default: FALSE)')
    
        # the custom parameter list
        self._parameters = []
        self.options = []

        self.defineParameters()

    def defineParameters(self):
        '''
        Define the parameters used by this app (abstract method in this class). 
        '''
        raise NotImplementedError("ChrisApp.defineParameters()")

    def run(self):
        '''
        Execute this app (abstract method in this class). 
        '''
        raise NotImplementedError("ChrisApp.run()")

    def add_argument(self, *args, **kwargs):
        '''
        Add a command line argument to this app. 
        '''
        try:
          name = kwargs['dest']
          type = kwargs['type']
          optional = kwargs['optional']
         except KeyError as e:
           detail = "%s parameter required. " % e 
            raise KeyError(detail)        

        # grab the optional, default and help values
        optional = True
        default = None
        help = None
        if 'default' in kwargs:
          default = kwargs['default']
        if 'help' in kwargs:
          help = kwargs['help']
        if 'optional' in kwargs:
          optional = kwargs['optional']

        # store the parameters internally    
        param = {'name': name, 'type': type, 'optional': optional,
                 'help': help, 'default': default}
        self._parameters.append(param)

        # add the argument to the parser
        del kwargs['optional']
        super(ChrisApp, self).add_argument(*args, **kwargs)

    def getJSONRepresentation():
        repres = {}
        repres['name'] = self.name
        repres['type'] = self.TYPE
        repres['parameters'] = self.parameters
        return repres

    def launch(self):
        '''
        This method triggers the parsing of arguments. The run() method gets called 
        if not --json or --description are specified.
        '''
        options = self.parse_args()
        self.options = options
        if (options.json):
          print(self.getJSONRpresentation())
        elif (options.description):
          print(self.getDescription())
        else:
          # run the app
          self.run()

    def error(self, message):
        '''
        The error handler if wrong commandline arguments are specified.
        '''
        print
        sys.stderr.write( 'ERROR: %s\n' % message )
        print
        self.print_help()
        sys.exit( 2 )

