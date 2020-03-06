
import logging
import time
import io
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from rest_framework import serializers

from pacsfiles.models import PACSFile
from pacsfiles.serializers import PACSFileSerializer
from pacsfiles.serializers import swiftclient


class PACSFileSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)

    def test_validate_path_failure_does_not_start_with_PACS(self):
        """
        Test whether overriden validate_path method validates submitted path must start
        with the 'PACS' string.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = 'cube/123456-Jorge/brain/brain_mri/file1.dcm'
        with self.assertRaises(serializers.ValidationError):
            pacsfiles_serializer.validate_path(path)

    def test_validate_path_failure_is_not_comprised_by_5_components(self):
        """
        Test whether overriden validate_path method validates submitted path must be
        comprized by 5 components:
        PACS/<MRN>-<PATIENTNAME>/<STUDY>/<SERIES>/<actualDICOMfile>.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = '/123456-Jorge/brain/brain_mri/file1.dcm'
        with self.assertRaises(serializers.ValidationError):
            pacsfiles_serializer.validate_path(path)

    def test_validate_path_failure_does_not_exist(self):
        """
        Test whether overriden validate_path method validates that submitted path exists
        in internal storage.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = 'PACS/123456-Jorge/brain/brain_mri/file1.dcm'
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
        path = 'PACS/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        with self.assertRaises(serializers.ValidationError):
            pacsfiles_serializer.validate_path(path)

    @tag('integration')
    def test_integration_validate_path_success(self):
        """
        Test whether overriden validate_path method validates submitted path.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = 'PACS/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
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
        Test whether overriden validate method updates validated data with the descriptors
        embedded in the path string.
        """
        pacsfiles_serializer = PACSFileSerializer()
        path = 'PACS/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        object_list = [{'name': path}]
        container_data = ['', object_list]
        with mock.patch.object(swiftclient.Connection, '__init__',
                               return_value=None) as conn_init_mock:
            with mock.patch.object(swiftclient.Connection, 'get_container',
                                   return_value=container_data) as conn_get_container_mock:
                new_data = pacsfiles_serializer.validate({'path': path})
                conn_init_mock.assert_called_with(user=settings.SWIFT_USERNAME,
                                                  key=settings.SWIFT_KEY,
                                                  authurl=settings.SWIFT_AUTH_URL)
                conn_get_container_mock.assert_called_with(settings.SWIFT_CONTAINER_NAME,
                                                   prefix=path)
                self.assertIn('mrn', new_data)
                self.assertIn('patient_name', new_data)
                self.assertIn('study', new_data)
                self.assertIn('series', new_data)
                self.assertIn('name', new_data)


    def test_validate_validates_path_has_not_already_been_registered(self):
        """
        Test whether overriden validate method validates that the submitted path
        has not been already registered.
        """
        path = 'PACS/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        object_list = [{'name': path}]
        container_data = ['', object_list]
        with mock.patch.object(swiftclient.Connection, '__init__',
                               return_value=None) as conn_init_mock:
            with mock.patch.object(swiftclient.Connection, 'get_container',
                                   return_value=container_data) as conn_get_container_mock:
                pacs_file = PACSFile(mrn='123456', patient_name='crazy',
                                     study='brain_crazy_study', series='brain_crazy_mri',
                                     name='file1.dcm')
                pacs_file.fname.name = path
                pacs_file.save()
                with self.assertRaises(serializers.ValidationError):
                    pacsfiles_serializer = PACSFileSerializer()
                    pacsfiles_serializer.validate({'path': path})
                conn_init_mock.assert_called_with(user=settings.SWIFT_USERNAME,
                                                  key=settings.SWIFT_KEY,
                                                  authurl=settings.SWIFT_AUTH_URL)
                conn_get_container_mock.assert_called_with(settings.SWIFT_CONTAINER_NAME,
                                                   prefix=path)
