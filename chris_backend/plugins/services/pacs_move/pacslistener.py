#!/usr/local/bin/python

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

import datetime

# Get current time
now = datetime.datetime.now().isoformat()
# write time to file
with open(os.path.join('/tmp', now+ '.txt'), 'w') as outfile:
    json.dump('Hello', outfile, indent=4, sort_keys=True, separators=(',', ':'))
