#                                                            _
# Simple chris fs app demo
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


class SimpleFSApp(ChrisApp):
    """
    Create file out.txt with the directory listing of the directory
    given by the --dir argument.
    """
    AUTHORS         = 'FNNDSC (dev@babyMRI.org)'
    SELFPATH        = os.path.dirname(__file__)
    SELFEXEC        = os.path.basename(__file__)
    TITLE           = 'Simple chris fs app'
    CATEGORY        = ''
    TYPE            = 'fs'
    DESCRIPTION     = 'A simple chris fs app demo'
    DOCUMENTATION   = 'http://wiki'
    LICENSE         = 'Opensource (MIT)'
    VERSION         = '0.1'

    def define_parameters(self):
        self.add_parameter('--dir', action='store', dest='dir', type=str, default='./',
                          optional=True, help='look up directory')

    def run(self, options):
        print(os.system('ls ' + options.dir + '>' + os.path.join(options.outputdir,
                                                                 'out.txt')))


# ENTRYPOINT
if __name__ == "__main__":
    app = SimpleFSApp()
    app.launch()
