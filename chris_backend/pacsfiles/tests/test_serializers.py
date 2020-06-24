
import logging
import time
import io
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from rest_framework import serializers

from pacsfiles.models import PACS, PACSFile
from pacsfiles.serializers import PACSFileSerializer
from pacsfiles.serializers import swiftclient


class PACSFileSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

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
        object_list = []
        container_data = ['', object_list]

        with mock.patch.object(swiftclient.Connection, '__init__',
                               return_value=None) as conn_init_mock:
            with mock.patch.object(swiftclient.Connection, 'get_container',
                                   return_value=container_data) as conn_get_container_mock:
                with self.assertRaises(serializers.ValidationError):
                    pacsfiles_serializer.validate_path(path)
                conn_init_mock.assert_called_with(user=settings.SWIFT_USERNAME,
                                                  key=settings.SWIFT_KEY,
                                                  authurl=settings.SWIFT_AUTH_URL)
                conn_get_container_mock.assert_called_with(settings.SWIFT_CONTAINER_NAME,
                                                   prefix=path)

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
        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # create container in case it doesn't already exist
        conn.put_container(settings.SWIFT_CONTAINER_NAME)

        # upload file to Swift storage
        with io.StringIO("test file") as file1:
            conn.put_object(settings.SWIFT_CONTAINER_NAME, path, contents=file1.read(),
                            content_type='text/plain')
        for _ in range(20):
            object_list = conn.get_container(settings.SWIFT_CONTAINER_NAME, prefix=path)[1]
            if object_list:
                break
            time.sleep(0.2)
        self.assertEqual(pacsfiles_serializer.validate_path(path), path)

        # delete file from Swift storage
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, path)

    def test_validate_updates_validated_data(self):
        """
        Test whether overriden validate method updates validated data with a PACS object.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file1.dcm'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
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
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS', 'path': path}
        pacs = PACS(identifier='MyPACS')
        pacs.save()
        pacs_file = PACSFile(PatientID='123456',
                             StudyInstanceUID='1.1.3432.54.6545674765.765434',
                             SeriesInstanceUID='2.4.3432.54.845674765.763345',
                             pacs=pacs)
        pacs_file.fname.name = path
        pacs_file.save()
        with self.assertRaises(serializers.ValidationError):
            pacsfiles_serializer = PACSFileSerializer()
            pacsfiles_serializer.validate(data)
