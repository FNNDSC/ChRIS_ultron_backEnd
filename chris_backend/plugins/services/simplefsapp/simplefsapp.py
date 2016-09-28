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


def touch(path):
    with open(path, 'a'):
        os.utime(path, None)

class SimpleFSApp(ChrisApp):
    """
    Create file out.txt with the directory listing of the directory
    given by the --dir argument.
    """
    AUTHORS         = 'FNNDSC (dev@babyMRI.org)'
    SELFPATH        = os.path.dirname(__file__)
    SELFEXEC        = os.path.basename(__file__)
    EXECSHELL       = 'python'
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
        str_outFile = os.path.join(options.outputdir, 'out.txt')
        print(os.system('ls ' + options.dir + '>' + str_outFile))

        # Create a 'dummy' listing of empty files mirroring the target dir listing
        with open(str_outFile) as f:
            l_ls    = f.readlines()
        print(l_ls)
        l_ls = map(str.strip, l_ls)
        for str_file in l_ls:
            str_fullPath    = os.path.join(options.outputdir, str_file)
            print('touching file... %s' % str_fullPath)
            touch(str_fullPath)


# ENTRYPOINT
if __name__ == "__main__":
    app = SimpleFSApp()
    app.launch()
