
import logging
import time
import io
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from rest_framework import serializers

from servicefiles.models import Service, ServiceFile
from servicefiles.serializers import ServiceFileSerializer
from servicefiles.serializers import SwiftManager


class ServiceFileSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_validate_service_name_failure_registered_service(self):
        """
        Test whether overriden validate_name method validates whether submitted
        unregistered service name is actually the name of a registered service.
        """
        servicefiles_serializer = ServiceFileSerializer()
        with self.assertRaises(serializers.ValidationError):
            servicefiles_serializer.validate_service_name('PACS')

    def test_validate_service_name_success(self):
        """
        Test whether overriden validate_name method successfully returns a valid
        unregistered service name.
        """
        Service.objects.get_or_create(identifier='NewService')
        servicefiles_serializer = ServiceFileSerializer()
        self.assertEqual(servicefiles_serializer.validate_service_name('MyService'),
                         'MyService')
        self.assertEqual(servicefiles_serializer.validate_service_name('NewService'),
                         'NewService')

    def test_validate_updates_validated_data(self):
        """
        Test whether overriden validate method updates validated data with the descriptors
        embedded in the path string.
        """
        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        data = {'service_name': 'MyService', 'path': path}
        servicefiles_serializer = ServiceFileSerializer()
        with mock.patch.object(SwiftManager, 'obj_exists',
                               return_value=True) as obj_exists_mock:
            new_data = servicefiles_serializer.validate(data)
            self.assertIn('service', new_data)
            self.assertNotIn('service_name', new_data)
            self.assertEqual(new_data.get('path'), path.strip(' ').strip('/'))
            obj_exists_mock.assert_called_with(new_data.get('path'))

    def test_validate_failure_path_does_not_start_with_SERVICES_PACS(self):
        """
        Test whether overriden validate method validates submitted path must start
        with the 'SERVICES/<service_name>/' string.
        """
        path = 'SERVICES/Other/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        data = {'service_name': 'MyService', 'path': path}
        servicefiles_serializer = ServiceFileSerializer()
        with self.assertRaises(serializers.ValidationError):
            servicefiles_serializer.validate(data)

    def test_validate_failure_path_does_not_exist(self):
        """
        Test whether overriden validate method validates that submitted path exists
        in internal storage.
        """
        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        data = {'service_name': 'MyService', 'path': path}
        servicefiles_serializer = ServiceFileSerializer()
        with mock.patch.object(SwiftManager, 'obj_exists',
                               return_value=False) as obj_exists_mock:
            with self.assertRaises(serializers.ValidationError):
                servicefiles_serializer.validate(data)
            obj_exists_mock.assert_called_with(path.strip(' ').strip('/'))

    @tag('integration')
    def test_integration_validate_path_failure_does_not_exist(self):
        """
        Test whether overriden validate method validates that submitted path exists
        in internal storage.
        """
        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        data = {'service_name': 'MyService', 'path': path}
        servicefiles_serializer = ServiceFileSerializer()
        with self.assertRaises(serializers.ValidationError):
            servicefiles_serializer.validate(data)

    @tag('integration')
    def test_integration_validate_path_success(self):
        """
        Test whether overriden validate method validates submitted path.
        """
        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        data = {'service_name': 'MyService', 'path': path}
        servicefiles_serializer = ServiceFileSerializer()

        swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                     settings.SWIFT_CONNECTION_PARAMS)
        # upload file to Swift storage
        with io.StringIO("test file") as file1:
            swift_manager.upload_obj(path, file1.read(), content_type='text/plain')
        for _ in range(20):
            if swift_manager.obj_exists(path):
                break
            time.sleep(0.2)
        self.assertEqual(servicefiles_serializer.validate(data).get('path'), path)

        # delete file from Swift storage
        swift_manager.delete_obj(path)

    def test_validate_validates_path_has_not_already_been_registered(self):
        """
        Test whether overriden validate method validates that the submitted path
        has not been already registered.
        """
        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        data = {'service_name': 'MyService', 'path': path}
        servicefiles_serializer = ServiceFileSerializer()
        service = Service(identifier='MyService')
        service.save()
        service_file = ServiceFile(service=service)
        service_file.fname.name = path
        service_file.save()
        with self.assertRaises(serializers.ValidationError):
            servicefiles_serializer.validate(data)
