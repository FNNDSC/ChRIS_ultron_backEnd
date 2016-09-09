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

        # query parameters
        #
        #
        #
        #
        query_settings = {
            'PatientID': '',
            'PatientName': '',
            'PatientSex': '',
            'StudyDate': '',
            'ModalitiesInStudy': '*R',
            'PerformedStationAETitle': '',
            'StudyDescription': '',
            'SeriesDescription': ''
        }

        # common options between all request types
        # aet
        # aec
        # ip
        # port
        pacs_settings = {
            'aet': 'CHRIS-ULTRON-AET',
            'aec': 'CHRIS-ULTRON-AEC',
            'server_ip': '192.168.1.110',
            'server_port': '4242'
        }
        pacs = PACS(pacs_settings)

        # echo the PACS to make sure we can access it
        # timeout
        echo = pacs.echo()
        if echo['status'] == 'error':
            with open(os.path.join(options.outputdir,echo['status'] + '.txt'), 'w') as outfile:
                json.dump(echo, outfile, indent=4, sort_keys=True, separators=(',', ':'))
            return

        # find in the PACS
        # find ALL by default (studies + series + images)
        # type: all, study, series, image
        # patient name
        # patient age
        # provide extra args for the find query
        find = pacs.find(query_settings)
        with open(os.path.join(options.outputdir,find['status'] + '.txt'), 'w') as outfile:
            json.dump(find, outfile, indent=4, sort_keys=True, separators=(',', ':'))

        print(find['data']['study'])

        return json.dumps(find)

# ENTRYPOINT
if __name__ == "__main__":
    app = PacsQueryApp()
    app.launch()
