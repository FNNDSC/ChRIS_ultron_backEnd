
import logging

from django.contrib.auth.models import User
from django.test import TestCase, tag
from django.conf import settings
from unittest import mock
from rest_framework import serializers

from pacsfiles.serializers import PACSSeriesSerializer


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class PACSSeriesSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


    def test_validate_ndicom_failure_not_positive(self):
        """
        Test whether overriden validate_ndicom method validates submitted ndicom must
        be a positive integer.
        """
        pacs_series_serializer = PACSSeriesSerializer()
        with self.assertRaises(serializers.ValidationError):
            pacs_series_serializer.validate_ndicom(0)

    def test_validate_ndicom_success(self):
        """
        Test whether overriden validate_ndicom method properly validates submitted ndicom.
        """
        pacs_series_serializer = PACSSeriesSerializer()
        self.assertEqual(pacs_series_serializer.validate_ndicom(1), 1)

    def test_validate_path_failure_does_not_start_with_SERVICES_PACS(self):
        """
        Test whether overriden validate_path method validates submitted path must start
        with the 'SERVICES/PACS/' string.
        """
        pacs_series_serializer = PACSSeriesSerializer()
        path = 'cube/123456-Jorge/brain/brain_mri'
        with self.assertRaises(serializers.ValidationError):
            pacs_series_serializer.validate_path(path)
        path = 'SERVICES/123456-Jorge/brain/brain_mri'
        with self.assertRaises(serializers.ValidationError):
            pacs_series_serializer.validate_path(path)


    def test_validate_path_success(self):
        """
        Test whether overriden validate_path method validates submitted path.
        """
        pacs_series_serializer = PACSSeriesSerializer()
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        self.assertEqual(pacs_series_serializer.validate_path(path), path)

    def test_validate_failure_path_does_not_start_with_SERVICES_PACS_pacs_name(self):
        """
        Test whether overriden validate method validates that submitted path must start
        with the 'SERVICES/PACS/pacs_name' string.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyDate': '2020-07-15',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS1', 'path': path, 'ndicom': 1}

        with self.assertRaises(serializers.ValidationError):
            pacs_series_serializer = PACSSeriesSerializer()
            pacs_series_serializer.validate(data)

    def test_validate_failure_ndicom_in_storage_different_from_request_data(self):
        """
        Test whether overriden validate method validates that submitted path must start
        with the 'SERVICES/PACS/pacs_name' string.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyDate': '2020-07-15',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS', 'path': path, 'ndicom': 2}


        storage_manager_mock = mock.Mock()
        storage_manager_mock.ls = mock.Mock(return_value=['file1'])

        with mock.patch('pacsfiles.serializers.connect_storage') as connect_storage_mock:
            connect_storage_mock.return_value = storage_manager_mock

            with self.assertRaises(serializers.ValidationError):
                pacs_series_serializer = PACSSeriesSerializer()
                pacs_series_serializer.validate(data)

    def test_validate_success(self):
        """
        Test whether overriden validate method correctly validates data.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyDate': '2020-07-15',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS', 'path': path, 'ndicom': 1}


        storage_manager_mock = mock.Mock()
        storage_manager_mock.ls = mock.Mock(return_value=[
            'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file1.dcm'])

        with mock.patch('pacsfiles.serializers.connect_storage') as connect_storage_mock:
            connect_storage_mock.return_value = storage_manager_mock
            pacs_series_serializer = PACSSeriesSerializer()
            pacs_series_serializer.validate(data)
            storage_manager_mock.ls.assert_called_with(path)
