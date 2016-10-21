#                                                            _
# Pacs query app
#
# (c) 2016 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#



import os, sys, json, pypx

# import the Chris app superclass
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from base import ChrisApp

class PacsQueryApp(ChrisApp):
    '''
    Create file out.txt witht the directory listing of the directory
    given by the --dir argument.
    '''
    AUTHORS = 'FNNDSC (dev@babyMRI.org)'
    SELFPATH        = os.path.dirname(__file__)
    SELFEXEC        = os.path.basename(__file__)
    EXECSHELL       = 'python3'
    TITLE = 'Pacs Query'
    CATEGORY = ''
    TYPE = 'fs'
    DESCRIPTION = 'An app to find data of interest on the PACS'
    DOCUMENTATION = 'http://wiki'
    LICENSE = 'Opensource (MIT)'
    VERSION = '0.1'

    def define_parameters(self):
        # PACS settings
        self.add_parameter('--aet', action='store', dest='aet', type=str, default='CHRIS-ULTRON-AET',optional=True, help='aet')
        self.add_parameter('--aec', action='store', dest='aec', type=str, default='CHRIS-ULTRON-AEC',optional=True, help='aec')
        self.add_parameter('--serverIP', action='store', dest='server_ip', type=str, default='192.168.1.110',optional=True, help='PACS server IP')
        self.add_parameter('--serverPort', action='store', dest='server_port', type=str, default='4242',optional=True, help='PACS server port')

        # Query settings
        self.add_parameter('--patientID', action='store', dest='patient_id', type=str, default='2175',optional=True, help='Patient ID')
        self.add_parameter('--patientName', action='store', dest='patient_name', type=str, default='',optional=True, help='Patient name')
        self.add_parameter('--patientSex', action='store', dest='patient_sex', type=str, default='',optional=True, help='Patient sex')
        self.add_parameter('--studyDate', action='store', dest='study_date', type=str, default='',optional=True, help='Study date (YYYY/MM/DD)')
        self.add_parameter('--modalitiesInStudy', action='store', dest='modalities_in_study', type=str, default='',optional=True, help='Modalities in study')
        self.add_parameter('--performedStationAETitle', action='store', dest='performed_station_aet', type=str, default='',optional=True, help='Performed station aet')
        self.add_parameter('--studyDescription', action='store', dest='study_description', type=str, default='',optional=True, help='Study description')
        self.add_parameter('--seriesDescription', action='store', dest='series_description', type=str, default='',optional=True, help='Series Description')


    def run(self, options):

        # common options between all request types
        # aet
        # aec
        # ip
        # port
        pacs_settings = {
            'aet': options.aet,
            'aec': options.aec,
            'server_ip': options.server_ip,
            'server_port': options.server_port
        }

        # echo the PACS to make sure we can access it
        echo = pypx.echo(pacs_settings)
        if echo['status'] == 'error':
            with open(os.path.join(options.outputdir,echo['status'] + '.txt'), 'w') as outfile:
                json.dump(echo, outfile, indent=4, sort_keys=True, separators=(',', ':'))
            return

        # find in the PACS
        # find ALL by default (studies + series + images)
        # type: all, study, series, image

        # query parameters
        query_settings = {
            'PatientID': options.patient_id,
            'PatientName': options.patient_name,
            'PatientSex': options.patient_sex,
            'StudyDate': options.study_date,
            'ModalitiesInStudy': options.modalities_in_study,
            'PerformedStationAETitle': options.performed_station_aet,
            'StudyDescription': options.study_description,
            'SeriesDescription': options.series_description
        }

        # python 3.5...
        find = pypx.find({**pacs_settings, **query_settings})
        with open(os.path.join(options.outputdir,find['status'] + '.txt'), 'w') as outfile:
            json.dump(find, outfile, indent=4, sort_keys=True, separators=(',', ':'))

        return json.dumps(find)

# ENTRYPOINT
if __name__ == "__main__":
    app = PacsQueryApp()
    app.launch()
