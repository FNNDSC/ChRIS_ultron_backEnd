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

from pacs_ping import PACSPing
from pacs_query import PACSQuery

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

        # ping the PACS
        ping = PACSPing(options)
        ping_response = ping.run()

        # query the PACS
        query = PACSQuery(options)
        query_response = query.run()
        # print(json.dumps(query_response))

        with open(os.path.join(options.outputdir,'query.txt'), 'w') as outfile:
            json.dump(query_response, outfile, indent=4, sort_keys=True, separators=(',', ':'))

        # if ping_response.success:
        #     pass
        # else:
        #     print('ping failed')

        # query the PACS

        # save response



# ENTRYPOINT
if __name__ == "__main__":
    app = PacsQueryApp()
    app.launch()
