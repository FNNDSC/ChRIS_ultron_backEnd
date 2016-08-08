#                                                            _
# Simple chris ds app demo
#
# (c) 2016 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#



import os, sys, shutil

# import the Chris app superclass
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from base import ChrisApp


class SimpleDSApp(ChrisApp):
    '''
    Add prefix given by the --prefix option to the name of each input file.
    '''
    AUTHORS = 'FNNDSC (dev@babyMRI.org)'
    TITLE = 'Simple chris ds app'
    CATEGORY = ''
    TYPE = 'ds'
    DESCRIPTION = 'A simple chris ds app demo'
    DOCUMENTATION = 'http://wiki'
    LICENSE = 'Opensource (MIT)'
    VERSION = '0.1'

    def define_parameters(self):
        self.add_parameter('--prefix', action='store', dest='prefix', type=str,
                          optional=False, help='prefix for file names')

    def run(self, options):
        for (dirpath, dirnames, filenames) in os.walk(options.inputdir):
            for dirname in dirnames:
                os.makedirs(os.path.join(output_path, dirnames))
            for name in filenames:
                new_name = options.prefix + name
                output_path =  os.path.join(options.outputdir,
                                            dirpath.replace(options.inputdir, ""))
                shutil.copy(os.path.join(dirpath, name), os.path.join(output_path, new_name))
            


# ENTRYPOINT
if __name__ == "__main__":
    app = SimpleApp()
    app.launch()
