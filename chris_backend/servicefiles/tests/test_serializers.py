
import logging
import time
import io
import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, tag
from django.conf import settings
from rest_framework import serializers

from servicefiles.models import Service, ServiceFile
from servicefiles.serializers import ServiceFileSerializer
from core.models import ChrisFolder
from core.storage.helpers import connect_storage, mock_storage

class ServiceFileSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = 'chris1234'
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)

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
        service_name = 'NewService'
        folder_path = f'SERVICES/{service_name}'
        owner = User.objects.get(username=self.chris_username)
        (service_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                owner=owner)

        Service.objects.get_or_create(folder=service_folder, identifier=service_name)
        servicefiles_serializer = ServiceFileSerializer()
        self.assertEqual(servicefiles_serializer.validate_service_name('MyService'),
                         'MyService')
        self.assertEqual(servicefiles_serializer.validate_service_name('NewService'),
                         'NewService')

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
        with mock_storage('servicefiles.serializers.settings'):
            with self.assertRaises(serializers.ValidationError):
                servicefiles_serializer.validate(data)

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

        storage_manager = connect_storage(settings)
        # upload file to storage
        with io.StringIO("test file") as file1:
            storage_manager.upload_obj(path, file1.read(), content_type='text/plain')
        for _ in range(20):
            if storage_manager.obj_exists(path):
                break
            time.sleep(0.2)
        self.assertEqual(servicefiles_serializer.validate(data).get('path'), path)

        # delete file from storage
        storage_manager.delete_obj(path)

    def test_validate_validates_path_has_not_already_been_registered(self):
        """
        Test whether overriden validate method validates that the submitted path
        has not been already registered.
        """
        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        service_name = 'MyService'
        data = {'service_name': service_name, 'path': path}
        servicefiles_serializer = ServiceFileSerializer()

        folder_path = f'SERVICES/{service_name}'
        owner = User.objects.get(username=self.chris_username)
        (service_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                owner=owner)
        service = Service(folder=service_folder, identifier=service_name)
        service.save()

        folder_path = os.path.dirname(path)
        (file_parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                    owner=owner)
        service_file = ServiceFile(owner=owner, parent_folder=file_parent_folder)
        service_file.fname.name = path
        service_file.save()
        with self.assertRaises(serializers.ValidationError):
            servicefiles_serializer.validate(data)
