import subprocess, re

class PACSFind():
    """docstring for PACSFind."""
    def __init__(self, command_suffix):
        self.executable = 'findscu'
        self.command_suffix = command_suffix
        # to be moved out
        self.postfilter_parameters = {
            'PatientSex': '',
            'PerformedStationAETitle': '',
            'StudyDescription': '',
            'SeriesDescription': ''
        }

    def commandStudy(self, opt={}):
        study_parameters = {
            'PatientID': '',
            'PatientName': '',
            'PatientBirthDate': '',
            'PatientSex': '',
            'StudyDate': '',
            'StudyDescription': '',
            'StudyInstanceUID': '',
            'ModalitiesInStudy': '',
            'PerformedStationAETitle': '',
            'QueryRetrieveLevel': 'STUDY'
        }

        # build query
        command = ' -xi'

        if 'PatientID' in opt and opt['PatientID'] != '':
            command += ' -P'
        else:
            command += ' -S'

        return self.commandWrap(command, study_parameters, opt)

    def commandSeries(self, opt={}):
        series_parameters = {
            'NumberOfSeriesRelatedInstances': '',
            'InstanceNumber': '',
            'SeriesDescription': '',
            'StudyInstanceUID': '',
            'SeriesInstanceUID': '',
            'QueryRetrieveLevel': 'SERIES'
        }

        # build query
        command = ' -xi'
        command += ' -S'

        return self.commandWrap(command, series_parameters, opt)

    def commandImage(self, opt={}):
        image_parameters = {
            'StudyInstanceUID': '',
            'SeriesInstanceUID': '',
            'QueryRetrieveLevel': 'IMAGE'
        }

        # build query
        command = ' -xi'
        command += ' -S'

        return self.commandWrap(command, image_parameters, opt)

    def commandWrap(self, command, parameters, opt={}):
        for key, value in parameters.items():
            # update value if provided
            if key in opt:
                value = opt[key]
            # update command
            if value != '':
                command += ' -k "' + key + '=' + value + '"'
            else:
                command += ' -k ' + key

        return self.executable + ' ' + command + ' ' + self.command_suffix

    def preparePostFilter(self):
        print('prepare post filter')
        # $post_filter['PatientSex'] = $patientsex;
        # $post_filter['PerformedStationAETitle'] = $station;
        # $post_filter['StudyDescription'] = $studydescription;
        # $post_filter['SeriesDescription'] = $seriesdescription;

    def run(self, opt={}):
        print('run PACSFind')
        #
        #
        # find study
        study_response = subprocess.run(self.commandStudy(opt), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        # format response
        study_response = self.formatResponse(study_response)
        study_response_container = {
            'status': 'success',
            'data': []
        }
        study_response_container['data'] += study_response['data']

        if study_response_container['status'] == 'error':
            return study_response_container

        #
        #
        # find series
        series_response_container = {
            'status': 'success',
            'data': []
        }

        for study in study_response_container['data']:
            opt['StudyInstanceUID'] = study['StudyInstanceUID']['value']
            series_response = subprocess.run(self.commandSeries(opt), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
            series_response = self.formatResponse(series_response)
            if series_response['status'] == 'error':
                series_response_container['status'] == 'error'
            series_response_container['data'] += series_response['data']

        if series_response_container['status'] == 'error':
            return series_response_container

        #
        #
        # find images
        image_response_container = {
            'status': 'success',
            'data': []
        }

        for series in series_response_container['data']:
            opt['StudyInstanceUID'] = series['StudyInstanceUID']['value']
            opt['SeriesInstanceUID'] = series['SeriesInstanceUID']['value']
            image_response = subprocess.run(self.commandImage(opt), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
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
        response = {
            'status': 'success',
            'data': '',
            'command': response.args
        }

        status = self.checkResponse(std)
        if status == 'error':
            response['status'] = 'error';
            response['data'] = std;
        else:
            response['status'] = 'success';
            response['data'] = self.parseResponse(std)

        return response
