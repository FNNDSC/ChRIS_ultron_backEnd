
import logging
import time
import io

from django.test import TestCase, tag
from django.conf import settings
from rest_framework import serializers

from pacsfiles.models import PACS, PACSFile
from pacsfiles.serializers import PACSFileSerializer
from core.storage.helpers import connect_storage, mock_storage


class PACSFileSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_validate_path_failure_does_not_start_with_SERVICES_PACS(self):
        """
        Test whether overriden validate_path method validates submitted path must start
        with the 'SERVICES/PACS/' string.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = 'cube/123456-Jorge/brain/brain_mri/file1.dcm'
        with self.assertRaises(serializers.ValidationError):
            pacsfiles_serializer.validate_path(path)
        path = 'SERVICES/123456-Jorge/brain/brain_mri/file1.dcm'
        with self.assertRaises(serializers.ValidationError):
            pacsfiles_serializer.validate_path(path)

    def test_validate_path_failure_does_not_exist(self):
        """
        Test whether overriden validate_path method validates that submitted path exists
        in internal storage.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = 'SERVICES/PACS/MyPACS/123456-Jorge/brain/brain_mri/file1.dcm'

        with mock_storage('pacsfiles.serializers.settings') as storage_manager:
            with self.assertRaises(serializers.ValidationError):
                pacsfiles_serializer.validate_path(path)
            expected_fname = path.strip(' ').strip('/')

            expected_errmsg = r'Could not find this path\.'
            with self.assertRaisesRegex(serializers.ValidationError, expected_errmsg):
                pacsfiles_serializer.validate_path(path)

            storage_manager.upload_obj(expected_fname, b'example data')
            pacsfiles_serializer.validate_path(path)  # expect to not raise an exception

    @tag('integration')
    def test_integration_validate_path_failure_does_not_exist(self):
        """
        Test whether overriden validate_path method validates that submitted path exists
        in internal storage.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file1.dcm'
        with self.assertRaises(serializers.ValidationError):
            pacsfiles_serializer.validate_path(path)

    @tag('integration')
    def test_integration_validate_path_success(self):
        """
        Test whether overriden validate_path method validates submitted path.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file1.dcm'
        storage_manager = connect_storage(settings)
        # upload file to storage
        with io.StringIO("test file") as file1:
            storage_manager.upload_obj(path, file1.read(), content_type='text/plain')

        for _ in range(20):
            if storage_manager.obj_exists(path):
                break
            time.sleep(0.2)
        self.assertEqual(pacsfiles_serializer.validate_path(path), path)

        # delete file from storage
        storage_manager.delete_obj(path)

    def test_validate_updates_validated_data(self):
        """
        Test whether overriden validate method updates validated data with a PACS object.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file1.dcm'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyDate': '2020-07-15',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'PatientSex':'O',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS', 'path': path}
        pacsfiles_serializer = PACSFileSerializer()
        new_data = pacsfiles_serializer.validate(data)
        self.assertIn('pacs', new_data)

    def test_validate_validates_path_has_not_already_been_registered(self):
        """
        Test whether overriden validate method validates that the submitted path
        has not been already registered.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file1.dcm'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyDate': '2020-07-15',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS', 'path': path}
        pacs = PACS(identifier='MyPACS')
        pacs.save()
        pacs_file = PACSFile(PatientID='123456',
                             StudyDate='2020-07-15',
                             StudyInstanceUID='1.1.3432.54.6545674765.765434',
                             SeriesInstanceUID='2.4.3432.54.845674765.763345',
                             pacs=pacs)
        pacs_file.fname.name = path
        pacs_file.save()
        with self.assertRaises(serializers.ValidationError):
            pacsfiles_serializer = PACSFileSerializer()
            pacsfiles_serializer.validate(data)
