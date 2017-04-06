#                                                            _
# Pacs query app
#
# (c) 2016 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#



import os
import sys
import json
import time
import shutil
import subprocess
import pypx

# import the Chris app superclass
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from base import ChrisApp

# dicom settings
#
DICOM = {}
DICOM['server_ip'] = '173.48.120.248'
DICOM['server_port'] = '4242'
DICOM['called_aet'] = 'ORTHANC'
DICOM['calling_aet'] = 'CHIPS'
DICOM['dicom_data'] = '/incoming/data/'

if 'DICOM_SERVER_IP' in os.environ:
    DICOM['server_ip'] = os.environ['DICOM_SERVER_IP']
if 'DICOM_SERVER_PORT' in os.environ:
    DICOM['server_port'] = os.environ['DICOM_SERVER_PORT']
if 'CALLING_AET' in os.environ:
    DICOM['calling_aet'] = os.environ['DICOM_CALLING_AET']
if 'CALLED_AET' in os.environ:
    DICOM['called_aet'] = os.environ['CALLED_AET']
if 'DICOM_DATA' in os.environ:
    DICOM['dicom_data'] = os.environ['DICOM_DATA']

class PacsRetrieveApp(ChrisApp):
    '''
    Create file out.txt witht the directory listing of the directory
    given by the --dir argument.
    '''
    AUTHORS = 'FNNDSC (dev@babyMRI.org)'
    SELFPATH = os.path.dirname(__file__)
    SELFEXEC = os.path.basename(__file__)
    EXECSHELL = 'python3'
    TITLE = 'Pacs Retrieve'
    CATEGORY = ''
    TYPE = 'ds'
    DESCRIPTION = 'An app to find data of interest on the PACS'
    DOCUMENTATION = 'http://wiki'
    LICENSE = 'Opensource (MIT)'
    VERSION = '0.1'

    def define_parameters(self):

        # PACS settings
        self.add_parameter(
            '--aet', action='store', dest='aet', type=str,
            default=DICOM['calling_aet'], optional=True, help='aet')
        self.add_parameter(
            '--aec', action='store', dest='aec', type=str,
            default=DICOM['called_aet'], optional=True, help='aec')
        self.add_parameter(
            '--aetListener', action='store', dest='aet_listener', type=str,
            default=DICOM['calling_aet'], optional=True, help='aet listener')
        self.add_parameter(
            '--serverIP', action='store', dest='server_ip', type=str,
            default=DICOM['server_ip'], optional=True, help='PACS server IP')
        self.add_parameter(
            '--serverPort', action='store', dest='server_port', type=str,
            default=DICOM['server_port'], optional=True, help='PACS server port')

        # Retrieve settings
        self.add_parameter(
            '--seriesUIDS', action='store', dest='series_uids', type=str,
            default=',', optional=True, help='Series UIDs to be retrieved')
        self.add_parameter(
            '--dataLocation', action='store', dest='data_location', type=str,
            default=DICOM['dicom_data'], optional=True,
            help='Location where the DICOM Listener receives the data.')

    def run(self, options):

        # options.inputdir

        # common options between all request types
        # aet
        # aec
        # aet_listener
        # ip
        # port
        pacs_settings = {
            'aet': options.aet,
            'aec': options.aec,
            'aet_listener': options.aet_listener,
            'server_ip': options.server_ip,
            'server_port': options.server_port
        }

        # echo the PACS to make sure we can access it
        pacs_settings['executable'] = '/usr/bin/echoscu'
        echo = pypx.echo(pacs_settings)
        if echo['status'] == 'error':
            with open(os.path.join(options.outputdir, echo['status'] + '.txt'), 'w') as outfile:
                json.dump(echo, outfile, indent=4, sort_keys=True, separators=(',', ':'))
            return

        # create dummy series file with all series
        series_file = os.path.join(options.inputdir, 'success.txt')

        # uids to be fetched from success.txt
        uids = options.series_uids.split(',')
        uids_set = set(uids)

        # parser series file
        data_file = open(series_file, 'r')
        data = json.load(data_file)
        data_file.close()
        filtered_uids = [
            series for series in data['data'] if str(series['uid']['value']) in uids_set]

        path_dict = []
        data_directory = options.data_location

        # create destination directories and move series
        pacs_settings['executable'] = '/usr/bin/movescu'

        for series in filtered_uids:
            patient_dir = pypx.utils.patientPath(
                '', series['PatientID']['value'],
                series['PatientName']['value'])
            study_dir = pypx.utils.studyPath(
                patient_dir, series['StudyDescription']['value'],
                series['StudyDate']['value'],
                series['StudyInstanceUID']['value'])
            series_dir = pypx.utils.seriesPath(
                study_dir, series['SeriesDescription']['value'],
                series['SeriesDate']['value'],
                series['SeriesInstanceUID']['value'])

            source = os.path.join(data_directory, series_dir)
            series_info = os.path.join(source, 'series.info')
            destination_study = os.path.join(options.outputdir, study_dir)
            destination_series = os.path.join(options.outputdir, series_dir)

            path_dict.append(
                {'source': source,
                 'destination_study': destination_study,
                 'destination_series': destination_series,
                 'info': series_info})

            # move series
            pacs_settings['series_uid'] = series['SeriesInstanceUID']['value']
            output = pypx.move(pacs_settings)


        print('Receiving data.')

        # wait for files to arrive!
        timer = 0

        while timer < 100: # 1h
            for path in path_dict[:]:

                # what if pulling an existing dataset
                # (.info file already there? need extra flag to force re=pull?)
                if os.path.isfile(path['info']):

                    if not os.path.exists(path['destination_study']):
                        os.makedirs(path['destination_study'])
                    else:
                        print(path['destination_study'] + ' already exists.')

                    # copy series to output
                    shutil.copytree(path['source'], path['destination_series'])

                    # create jpgs directory
                    destination_jpgs = os.path.join(path['destination_series'], 'jpgs')
                    if not os.path.exists(destination_jpgs):
                        os.makedirs(destination_jpgs)
                    else:
                        print(destination_jpgs + ' already exists.')

                    # generate jpgs for all dcm files
                    for filename in os.listdir(path['destination_series']):
                        name, extension = os.path.splitext(filename)
                        if extension == '.dcm':
                            basename = os.path.basename(filename)
                            source = os.path.join(path['destination_series'], basename)
                            output = os.path.join(destination_jpgs, basename)
                            exec_location = os.path.dirname(pacs_settings['executable'])
                            executable = os.path.join(exec_location, 'dcmj2pnm')
                            command = executable + ' +oj +Wh 15 +Fa ' + source + ' ' + output + '.jpg';
                            response = subprocess.run(
                                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

                    # resize all jpgs
                    executable = '/usr/bin/mogrify'
                    options = '-resize 96x96 -background none -gravity center -extent 96x96'
                    source = os.path.join(destination_jpgs, '*')
                    command = executable + ' ' + options + ' ' + source
                    response = subprocess.run(
                        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

                    # create preview
                    executable = '/usr/bin/convert'
                    options = '-append'
                    output = os.path.join(path['destination_series'], 'preview.jpg')
                    command = executable + ' ' + options + ' ' + source + ' ' + output
                    response = subprocess.run(
                        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

                    # remove from dictionnary
                    path_dict.remove(path)

            if len(path_dict) == 0:
                break

            time.sleep(1)
            timer += 1

        print('Done.')

# ENTRYPOINT
if __name__ == "__main__":
    app = PacsRetrieveApp()
    app.launch()
