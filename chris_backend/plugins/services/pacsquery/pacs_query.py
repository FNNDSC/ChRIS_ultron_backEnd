import re, json

from pacs_base import PACSBase

class PACSQuery(PACSBase):
    """docstring for PACSQuery."""
    def __init__(self, arg):
        super(PACSQuery, self).__init__(arg)
        self.arg = arg
        self.arg.parameters = {}
        self.executable = 'findscu'

        self.study_parameters = {
            'PatientID': '',
            'PatientName': '',
            'PatientBirthDate': '',
            'PatientSex': '',
            'StudyDate': '',
            'StudyDescription': '',
            'StudyInstanceUID': '',
            'ModalitiesInStudy': '',
            'PerformedStationAETitle': '',
            'QueryRetrieveLevel': ''
        }

        self.series_parameters = {
            'NumberOfSeriesRelatedInstances': '',
            'InstanceNumber': '',
            'SeriesDescription': '',
            'StudyInstanceUID': '',
            'SeriesInstanceUID': '',
            'QueryRetrieveLevel': ''
        }

        self.image_parameters = {
            'StudyInstanceUID': '',
            'SeriesInstanceUID': '',
            'QueryRetrieveLevel': ''
        }

        self.postfilter_parameters = {
            'PatientSex': '',
            'PerformedStationAETitle': '',
            'StudyDescription': '',
            'SeriesDescription': ''
        }

    def prepareStudyQuery(self):
        print('prepare study query')

        self.study_parameters['QueryRetrieveLevel'] = 'STUDY'

        # TODO: loop through all study arguments
        if 'PatientID' in self.arg.parameters:
            self.study_parameters['PatientID'] = self.arg.parameters['PatientID']

        if 'PatientName' in self.arg.parameters:
            self.study_parameters['PatientName'] = self.arg.parameters['PatientName']

        if 'StudyDate' in self.arg.parameters:
            self.study_parameters['StudyDate'] = self.arg.parameters['StudyDate']

        if 'Modality' in self.arg.parameters:
            self.study_parameters['Modality'] = self.arg.parameters['Modality']

        # build query
        self.query = ' -xi'

        if 'PatientID' in self.study_parameters and self.study_parameters['PatientID'] != '':
            self.query += ' -P'
        else:
            self.query += ' -S'

        for key, value in self.study_parameters.items():
            if value != '':
                self.query += ' -k "' + key + '=' + value + '"'
                self.study_parameters[key] = ''
            else:
                self.query += ' -k ' + key

        print(self.query)

    def prepareSeriesQuery(self):
        print('prepare series query')

        self.series_parameters['QueryRetrieveLevel'] = 'SERIES'

        #TODO: loop through all series arguments

        # build query
        self.query = ' -xi'
        self.query += ' -S'

        for key, value in self.series_parameters.items():
            if value != '':
                self.query += ' -k "' + key + '=' + value + '"'
                self.series_parameters[key] = ''
            else:
                self.query += ' -k ' + key

        print(self.query)

    def prepareImageQuery(self):
        print('prepare image query')
        self.image_parameters['QueryRetrieveLevel'] = 'IMAGE'

        # build query
        self.query = ' -xi'
        self.query += ' -S'

        for key, value in self.image_parameters.items():
            if value != '':
                self.query += ' -k "' + key + '=' + value + '"'
                self.image_parameters[key] = ''
            else:
                self.query += ' -k ' + key

        print(self.query)

    def preparePostFilter(self):
        print('prepare post filter')
        # $post_filter['PatientSex'] = $patientsex;
        # $post_filter['PerformedStationAETitle'] = $station;
        # $post_filter['StudyDescription'] = $studydescription;
        # $post_filter['SeriesDescription'] = $seriesdescription;

    def run(self):
        # self.server_port = '4241'
        # prepare the study query parameters
        self.prepareStudyQuery()
        # prepare and run the command
        study_response = super(PACSQuery, self).run()
        # format response
        study_response = self.formatResponse(study_response)
        study_response_container = {
            'status': 'success',
            'data': []
        }
        study_response_container['data'] += study_response['data']

        if study_response_container['status'] == 'error':
            return study_response_container

        # loop through studies
        series_response_container = {
            'status': 'success',
            'data': []
        }

        for study in study_response_container['data']:
            self.series_parameters['StudyInstanceUID'] = study['StudyInstanceUID']['value']
            self.prepareSeriesQuery()
            series_response = super(PACSQuery, self).run()
            series_response = self.formatResponse(series_response)
            if series_response['status'] == 'error':
                series_response_container['status'] == 'error'
            series_response_container['data'] += series_response['data']

        if series_response_container['status'] == 'error':
            return series_response_container

        # loop through
        # series$this->addParameter('StudyInstanceUID', $seriesvalue);
        # $this->addParameter('SeriesInstanceUID', $resultseries['SeriesInstanceUID'][$j]);
        image_response_container = {
            'status': 'success',
            'data': []
        }

        for series in series_response_container['data']:
            self.image_parameters['StudyInstanceUID'] = series['StudyInstanceUID']['value']
            self.image_parameters['SeriesInstanceUID'] = series['SeriesInstanceUID']['value']
            self.prepareImageQuery()
            image_response = super(PACSQuery, self).run()
            image_response = self.formatResponse(image_response)
            if image_response['status'] == 'error':
                image_response_container['status'] == 'error'
            image_response_container['data'] += image_response['data']

        if image_response_container['status'] == 'error':
            return image_response_container

        response = {
            'status': 'success',
            'data': {
                'study': study_response_container['data'],
                'series': series_response_container['data'],
                'image': image_response_container['data']
            }
        }

        return response

    def checkResponse(self, response):
        stdSplit = response.split('\n')
        infoCount = 0
        errorCount = 0
        for line in stdSplit:
            if line.startswith('I: '):
                infoCount += 1
            elif line.startswith('E: '):
                errorCount += 1

        status = 'error'
        if errorCount == 0:
            status = 'success'

        return status

    def parseResponse(self, response):
        print('Parse response')
        data = []

        stdSplit = response.split('\n')

        for line in stdSplit:
            if line.startswith('I: ---------------------------'):
                data.append({})
            elif line.startswith('I: '):
                lineSplit = line.split()
                if len(lineSplit) >= 8 and re.search('\((.*?)\)', lineSplit[1]) != None:
                    # extract DICOM tag
                    tag = re.search('\((.*?)\)', lineSplit[1]).group(0)[1:-1].strip().replace('\x00', '')

                    # extract value
                    value = re.search('\[(.*?)\]', line)
                    if value != None:
                        value = value.group(0)[1:-1].strip().replace('\x00', '')
                    else:
                        value = 'no value provided'

                    # extract label
                    label = lineSplit[-1].strip()

                    data[-1][label] = {}
                    data[-1][label]['tag'] = tag
                    data[-1][label]['value'] = value
                    data[-1][label]['label'] = label

        return data

    def formatResponse(self, response):
        std = response.stdout.decode('ascii')

        status = self.checkResponse(std)
        if status == 'error':
            self.response['status'] = 'error';
            self.response['data'] = std;
        else:
            self.response['status'] = 'success';
            self.response['data'] = self.parseResponse(std)

        return self.response
