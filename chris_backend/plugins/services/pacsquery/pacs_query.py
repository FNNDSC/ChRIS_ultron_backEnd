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
            'SeriesDescription': ''
        }

        self.image_parameters = {}

        self.postfilter_parameters = {
            'PatientSex': '',
            'PerformedStationAETitle': '',
            'StudyDescription': '',
            'SeriesDescription': ''
        }

    def prepareStudyQuery(self):
        print('prepare study query')

        print(self.study_parameters)
        self.study_parameters['QueryRetrieveLevel'] = 'STUDY'

        if 'PatientID' in self.arg.parameters:
            self.study_parameters['PatientID'] = self.arg.parameters['PatientID']

        if 'PatientName' in self.arg.parameters:
            self.study_parameters['PatientName'] = self.arg.parameters['PatientName']

        if 'StudyDate' in self.arg.parameters:
            self.study_parameters['StudyDate'] = self.arg.parameters['StudyDate']

        if 'Modality' in self.arg.parameters:
            self.study_parameters['Modality'] = self.arg.parameters['Modality']

        # build query and reset study parameters
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

        print(self.study_parameters)
        print(self.query)

    def prepareSeriesQuery(self):
        print('prepare series query')
        self.query = '' #5s timeout

    def prepareImageQuery(self):
        print('prepare image query')
        self.query = '' #5s timeout

    def preparePostFilter(self):
        print('prepare post filter')
        # $post_filter['PatientSex'] = $patientsex;
        # $post_filter['PerformedStationAETitle'] = $station;
        # $post_filter['StudyDescription'] = $studydescription;
        # $post_filter['SeriesDescription'] = $seriesdescription;

    def run(self):
        # prepare the study query parameters
        self.prepareStudyQuery()
        # prepare and run the command
        study_response = super(PACSQuery, self).run()
        # handle response
        self.handleStudy(study_response)

        # prepare the series query parameters

        # prepare and run the command

        # handle response

    def handleStudy(self, study_response):
        print('handle Study PACSQuery')
        print(study_response)
        stdout = study_response.stdout.decode('ascii')
        stderr = study_response.stderr.decode('ascii')
        print(stdout)
        print(stderr)
