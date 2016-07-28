#                                                            _
# Simple chris app demo
#
# (c) 2016 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#



import os, sys

# import the Chris app superclass
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from base import ChrisApp


class SimpleApp(ChrisApp):
    '''
    '''
    AUTHORS = 'FNNDSC (dev@babyMRI.org)'
    TITLE = 'Simple chris app'
    CATEGORY = ''
    TYPE = 'fs'
    DESCRIPTION = 'A simple chris app demo'
    DOCUMENTATION = 'http://wiki'
    LICENSE = 'Opensource (MIT)'
    VERSION = '0.1'

    def define_parameters(self):
        self.add_parameter('--dir', action='store', dest='dir', type=str, default='./',
                          optional=True, help='look up directory')

    def run(self):
        print(os.system('ls ' + self.options.dir))


# ENTRYPOINT
if __name__ == "__main__":
    app = SimpleApp()
    app.launch()
