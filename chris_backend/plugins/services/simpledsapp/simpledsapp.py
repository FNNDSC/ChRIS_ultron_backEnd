#                                                            _
# Simple chris ds app demo
#
# (c) 2016 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#



import os, sys, shutil, time

# import the Chris app superclass
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from base import ChrisApp


class SimpleDSApp(ChrisApp):
    '''
    Add prefix given by the --prefix option to the name of each input file.
    '''
    AUTHORS         = 'FNNDSC (dev@babyMRI.org)'
    SELFPATH        = os.path.dirname(__file__)
    SELFEXEC        = os.path.basename(__file__)
    EXECSHELL       = 'python3'
    TITLE           = 'Simple chris ds app'
    CATEGORY        = ''
    TYPE            = 'ds'
    DESCRIPTION     = 'A simple chris ds app demo'
    DOCUMENTATION   = 'http://wiki'
    LICENSE         = 'Opensource (MIT)'
    VERSION         = '0.1'

    def define_parameters(self):

        self.add_parameter('--prefix', action='store', dest='prefix', type=str,
                          optional=False, help='prefix for file names')
        self.add_parameter('--sleepLength',
                           action   = 'store',
                           dest     = 'sleepLength',
                           type     = str,
                           optional = True,
                           help     ='prefix for file names',
                           default  = '0')

    def run(self, options):

        time.sleep(int(options.sleepLength))
        print('sleeping for %s' % options.sleepLength)
        for (dirpath, dirnames, filenames) in os.walk(options.inputdir):
            relative_path  = dirpath.replace(options.inputdir, "").strip("/")
            output_path =  os.path.join(options.outputdir, relative_path)
            for dirname in dirnames:
                print('Creating directory... %s' % os.path.join(output_path, dirname))
                os.makedirs(os.path.join(output_path, dirname))
            for name in filenames:
                new_name    = options.prefix + name
                str_outpath = os.path.join(output_path, new_name)
                print('Creating new file... %s' % str_outpath)
                shutil.copy(os.path.join(dirpath, name), str_outpath)
            


# ENTRYPOINT
if __name__ == "__main__":
    app = SimpleDSApp()
    app.launch()
