
import logging
import os
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.conf import settings
from rest_framework import serializers

from core.models import ChrisFolder
from userfiles.models import UserFile
from userfiles.serializers import UserFileSerializer


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class UserFileSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.username = 'test'
        self.password = 'testpass'

        # create user and its home folder
        user = User.objects.create_user(username=self.username,
                                        password=self.password)
        ChrisFolder.objects.get_or_create(path=f'home/{self.username}', owner=user)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_create(self):
        """
        Test whether overriden 'create' method successfully creates a new UserFile with
        the correct path and parent folder
        """
        user = User.objects.get(username=self.username)
        f = ContentFile('Test file'.encode())
        f.name = 'file1.txt'
        validated_data = {'upload_path': f'home/{self.username}/uploads/file1.txt',
                          'owner': user, 'fname': f}
        userfiles_serializer = UserFileSerializer()
        user_file = userfiles_serializer.create(validated_data)
        self.assertEqual(user_file.fname.name, f'home/{self.username}/uploads/file1.txt')
        self.assertEqual(user_file.parent_folder.path, f'home/{self.username}/uploads')

    def test_update(self):
        """
        Test whether overriden 'update' method successfully updates a UserFile with
        the correct path and parent folder
        """
        owner = User.objects.get(username=self.username)
        upload_path = f'home/{self.username}/uploads/file1.txt'
        folder_path = os.path.dirname(upload_path)
        (parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                               owner=owner)
        user_file = UserFile(parent_folder=parent_folder, owner=owner)
        user_file.fname.name = upload_path
        user_file.save()

        userfiles_serializer = UserFileSerializer()
        validated_data = {'upload_path': f'home/{self.username}/tests/file1.txt'}

        storage_manager_mock = mock.Mock()
        storage_manager_mock.copy_obj = mock.Mock()
        storage_manager_mock.delete_obj = mock.Mock()

        with mock.patch('userfiles.serializers.connect_storage') as connect_storage_mock:
            connect_storage_mock.return_value=storage_manager_mock
            user_file = userfiles_serializer.update(user_file, validated_data)
            storage_manager_mock.copy_obj.assert_called_with(upload_path, f'home/{self.username}/tests/file1.txt')
            self.assertEqual(user_file.fname.name,f'home/{self.username}/tests/file1.txt')
            self.assertEqual(user_file.parent_folder.path, f'home/{self.username}/tests')
            connect_storage_mock.assert_called_with(settings)
            storage_manager_mock.delete_obj.assert_called_with(upload_path)

    def test_validate_upload_path_failure_uploading_link_file(self):
        """
        Test whether overriden validate_upload_path method validates submitted path
        does not end with the .chrislink string.
        """
        userfiles_serializer = UserFileSerializer()
        request = mock.Mock()
        request.user = User.objects.get(username=self.username)
        with mock.patch.dict(userfiles_serializer.context,
                             {'request': request}, clear=True):
            with self.assertRaises(serializers.ValidationError):
                upload_path = f'home/{self.username}/uploads/mylink.chrislink'
                userfiles_serializer.validate_upload_path(upload_path)

    def test_validate_upload_path_failure_does_not_start_with_home(self):
        """
        Test whether overriden validate_upload_path method validates submitted path
        must start with the 'home/' string.
        """
        userfiles_serializer = UserFileSerializer()
        request = mock.Mock()
        request.user = User.objects.get(username=self.username)
        with mock.patch.dict(userfiles_serializer.context,
                             {'request': request}, clear=True):
            with self.assertRaises(serializers.ValidationError):
                userfiles_serializer.validate_upload_path('home')
            with self.assertRaises(serializers.ValidationError):
                userfiles_serializer.validate_upload_path('random/file1.txt')

    def test_validate_upload_path_failure_does_not_have_write_permission(self):
        """
        Test whether overriden validate_upload_path method validates submitted path
        must start with the 'home/<username>/' string.
        """
        userfiles_serializer = UserFileSerializer()
        request = mock.Mock()
        request.user = User.objects.get(username=self.username)
        with mock.patch.dict(userfiles_serializer.context,
                             {'request': request}, clear=True):
            with self.assertRaises(serializers.ValidationError):
                userfiles_serializer.validate_upload_path('SERVICES/PACS/random/file1.txt')

    @tag('integration')
    def test_validate_upload_path_success(self):
        """
        Test whether overriden validate_upload_path method validates submitted path.
        """
        userfiles_serializer = UserFileSerializer()
        request = mock.Mock()
        request.user = User.objects.get(username=self.username)

        with mock.patch.dict(userfiles_serializer.context,
                             {'request': request}, clear=True):
            upload_path = f'home/{self.username}/uploads/file1.txt'
            self.assertEqual(userfiles_serializer.validate_upload_path(upload_path),
                             upload_path)
