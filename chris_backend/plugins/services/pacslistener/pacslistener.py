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



import os, sys, json
import subprocess

import datetime
import uuid

# import dicom

# generate uuid for this incoming data
tmp_directory_base = '/tmp'
os.makedirs(tmp_directory_base, exist_ok=True)

log_directory = '/tmp/log'
os.makedirs(log_directory, exist_ok=True)

data_directory = '/tmp/data'
os.makedirs(data_directory, exist_ok=True)
# tmp directory
# log directory
# final directory


# create temporary directory
uuid = str(uuid.uuid4())
#print(uuid)
tmp_directory = os.path.join( tmp_directory_base, uuid)

# generate an error :)
# os.makedirs(tmp_directory)

try:
    os.makedirs(tmp_directory)
except OSError as e:
    errorfile = open(os.path.join(log_directory, 'error-' + uuid + '.txt'), 'w')
    errorfile.write('Error number: ' + str(e.errno) + '\n')
    errorfile.write('File name: ' + e.filename + '\n')
    errorfile.write('Error message: ' + e.strerror + '\n')
    errorfile.close()

command = '/usr/local/bin/storescp -id -od "' + tmp_directory + '" -xcr "touch ' + tmp_directory + '/#c;touch ' + tmp_directory + '/#a" -pm -sp;'
subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

rel_files = os.listdir(tmp_directory)
abs_files = list(map( lambda x: (tmp_directory + '/%s') % x, rel_files))
abs_dirs = filter(os.path.isdir, abs_files)

outputfile = open(os.path.join(log_directory, 'output-' + uuid + '.txt'), 'w')
outputfile.write( 'TMP DIRECTORY:' + '\n')
outputfile.write( tmp_directory + '\n')
outputfile.write( 'TMP FILES:' + '\n')
outputfile.write( '\n'.join(abs_files) + '\n')
outputfile.write( 'TMP DIRECTORIES:' + '\n')
outputfile.write( '\n'.join(abs_dirs))
outputfile.close()

# patient
# lookup patient directory with same patient info

# create patient directory
# $patientdirname = CHRIS_DATA.'/'.$process_file['PatientID'][0].'-'.$patient_chris_id;

# patient.info

# create study directory
# $studydirname = $patientdirname.'/'.$study_description.'-'.$study_chris_id;

# study.info

# create series directory
# $datadirname = $studydirname.'/'.$series_description.'-'.$data_chris_id;

# series.info

# move files
# $filename = $datadirname .'/'.$instance_nb.'-'. $process_file['SOPInstanceUID'][0] . '.dcm';

# cleanup

#print( p.stdout.read() )
