#!/usr/bin/env /Library/Frameworks/Python.framework/Versions/3.5/bin/python3
#                                                            _
# Pacs query app
#
# (c) 2016 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#



import os, sys
import subprocess
import datetime
import uuid
import shutil
import dicom

class PACSListener():

    def __init__(self):

        self.tmp_directory = '/tmp'
        self.log_directory = '/tmp/log'
        self.data_directory = '/tmp/data'

        os.makedirs(self.tmp_directory, exist_ok=True)
        os.makedirs(self.log_directory, exist_ok=True)
        os.makedirs(self.data_directory, exist_ok=True)

        # create unique directory to store inconming data
        self.uuid = str(uuid.uuid4())
        self.uuid_directory = os.path.join( self.tmp_directory, self.uuid)
        self.log_error = os.path.join(self.log_directory, 'err-' + self.uuid + '.txt')
        self.log_output = os.path.join(self.log_directory, 'out-' + self.uuid + '.txt')

        try:
            os.makedirs(self.uuid_directory)
        except OSError as e:
            errorfile = open(self.log_error, 'w')
            errorfile.write('Make ' + self.uuid_directory + ' directory\n')
            errorfile.write('Error number: ' + str(e.errno) + '\n')
            errorfile.write('File name: ' + e.filename + '\n')
            errorfile.write('Error message: ' + e.strerror + '\n')
            errorfile.close()

    def sanitize(self, value):

        # convert to string and remove trailing spaces
        tvalue = str(value).strip()
        # only keep alpha numeric characters and replace the rest by "_"
        svalue = "".join(character if character.isalnum() else '.' for character in tvalue )
        return svalue

    def mkdir(self, path):
        
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                errorfile = open(self.log_error, 'w')
                errorfile.write('Make ' + path + ' directory\n')
                errorfile.write('Error number: ' + str(e.errno) + '\n')
                errorfile.write('File name: ' + e.filename + '\n')
                errorfile.write('Error message: ' + e.strerror + '\n')
                errorfile.close()

        if not os.path.exists(path):
            errorfile = open(self.log_error, 'w')
            errorfile.write('PatientDirectory doesn\'t exist:' + path + '\n')
            errorfile.close()
            raise NameError('PatientDirectory doesn\'t exist:' + path)

    def run(self):

        # start listening to incoming data
        command = '/usr/local/bin/storescp -id -od "' + self.uuid_directory + '" -xcr "touch ' + self.uuid_directory + '/#c;touch ' + self.uuid_directory + '/#a" -pm -sp;'
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

        abs_files = [os.path.join(self.uuid_directory,f) for f in os.listdir(self.uuid_directory)]
        abs_dirs =  [f for f in list(abs_files) if os.path.isdir(f)]

        # Start logging
        outputfile = open(self.log_output, 'w')
        outputfile.write( 'UUID DIRECTORY:' + '\n')
        outputfile.write( self.uuid_directory + '\n')

        for directory in abs_dirs:

            outputfile.write( '>>>>>>>>>>> ' + directory + '\n')
            for data in os.listdir(directory):

                outputfile.write( '+++++ ' + data + '\n')
                abs_data = os.path.join(directory, data)
                dcm_info = dicom.read_file(abs_data)

                # patient info
                patient_id = self.sanitize(dcm_info.PatientID)
                patient_name = self.sanitize(dcm_info.PatientName)
                outputfile.write( 'PatientID: ' + patient_id + '\n')
                outputfile.write( 'PatientName: ' + patient_name + '\n')

                abs_patient = os.path.join(self.data_directory, patient_id + '-' + patient_name)
                self.mkdir(abs_patient)

                # patient.info file

                # study info
                study_description = self.sanitize(dcm_info.StudyDescription)
                study_date = self.sanitize(dcm_info.StudyDate)
                study_uid = self.sanitize(dcm_info.StudyInstanceUID)
                outputfile.write( 'StudyDescription: ' + study_description + '\n')
                outputfile.write( 'StudyDate: ' + study_date + '\n')
                outputfile.write( 'StudyInstanceUID: ' + study_uid + '\n')

                abs_study = os.path.join(abs_patient, study_description + '-' + study_date + '-' + study_uid)
                self.mkdir(abs_study)

                # study.info file

                # series info
                series_description = self.sanitize(dcm_info.SeriesDescription)
                series_date = self.sanitize(dcm_info.SeriesDate)
                series_uid = self.sanitize(dcm_info.SeriesInstanceUID)
                outputfile.write( 'SeriesDescription: ' + series_description + '\n')
                outputfile.write( 'SeriesDate: ' + series_date + '\n')
                outputfile.write( 'SeriesInstanceUID: ' + series_uid + '\n')

                abs_series = os.path.join(abs_study, series_description + '-' + series_date + '-' + series_uid)
                self.mkdir(abs_series)

                # series.info file

                # image info
                image_uid = self.sanitize(dcm_info.SOPInstanceUID)
                image_instance_number = self.sanitize(dcm_info.InstanceNumber)
                outputfile.write( 'SOPInstanceUID: ' + image_uid + '\n')
                outputfile.write( 'InstanceNumber: ' + image_instance_number + '\n')

                abs_image = os.path.join(abs_series, image_instance_number + '-' + image_uid + '.dcm')

                if not os.path.exists(abs_image):
                    try:
                        shutil.copy2(abs_data, abs_image)
                    except OSError as e:
                        errorfile = open(self.log_error, 'w')
                        errorfile.write('Copy ' + abs_data + ' to ' + self.abs_image + '\n')
                        errorfile.write('Error number: ' + str(e.errno) + '\n')
                        errorfile.write('File name: ' + e.filename + '\n')
                        errorfile.write('Error message: ' + e.strerror + '\n')
                        errorfile.close()

                if not os.path.exists(abs_image):
                    errorfile = open(self.log_error, 'w')
                    errorfile.write('PatientDirectory doesn\'t exist:' + abs_image + '\n')
                    errorfile.close()
                    raise NameError('PatientDirectory doesn\'t exist:' + abs_image)

                # image.info file

                # cleanup
                try:
                    shutil.rmtree(self.uuid_directory)
                except OSError as e:
                    errorfile = open(self.log_error, 'w')
                    errorfile.write('Remove ' + self.uuid_directory + ' tree\n')
                    errorfile.write('Error number: ' + str(e.errno) + '\n')
                    errorfile.write('File name: ' + e.filename + '\n')
                    errorfile.write('Error message: ' + e.strerror + '\n')
                    errorfile.close()
                # what about log files?

        outputfile.close() 

# start listener
pacs_listener = PACSListener()
pacs_listener.run()