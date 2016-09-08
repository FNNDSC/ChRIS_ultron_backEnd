#                                                            _
# Pacs query app
#
# (c) 2016 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#



import os, sys, json

# import the Chris app superclass
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from base import ChrisApp

from pacs import PACS

class PacsQueryApp(ChrisApp):
    '''
    Create file out.txt witht the directory listing of the directory
    given by the --dir argument.
    '''
    AUTHORS = 'FNNDSC (dev@babyMRI.org)'
    TITLE = 'Pacs Query'
    CATEGORY = ''
    TYPE = 'fs'
    DESCRIPTION = 'An app to find data of interest on the PACS'
    DOCUMENTATION = 'http://wiki'
    LICENSE = 'Opensource (MIT)'
    VERSION = '0.1'

    def define_parameters(self):
        self.add_parameter('--dir', action='store', dest='dir', type=str, default='./',optional=True, help='look up directory')

    def run(self, options):
        print(os.system('ls ' + options.dir + '>' + os.path.join(options.outputdir,'out.txt')))

        # common options between all request types
        # aet
        # aec
        # ip
        # port
        pacs = PACS(options)

        # echo the PACS to make sure we can access it
        # timeout
        echo = pacs.echo()

        # find in the PACS
        # find ALL by default (studies + series + images)
        # type: all, study, series, image
        # patient name
        # patient age
        # provide extra args for the find query
        find = pacs.find()
        print(find)

        with open(os.path.join(options.outputdir,'query.txt'), 'w') as outfile:
            json.dump(find, outfile, indent=4, sort_keys=True, separators=(',', ':'))



# ENTRYPOINT
if __name__ == "__main__":
    app = PacsQueryApp()
    app.launch()
