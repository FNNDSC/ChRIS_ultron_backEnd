
import logging
import os
from unittest import mock

from django.test import TestCase
from django.contrib.auth.models import User

from core.models import ChrisFolder, ChrisFile


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # superuser chris (owner of root folders)
        self.chris_username = 'chris'

        # create normal user
        self.username = 'foo'
        self.password = 'bar'
        User.objects.create_user(username=self.username, password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class ChrisFileModelTests(ModelTests):

    def setUp(self):
        super(ChrisFileModelTests, self).setUp()

        # create a ChrisFile instance
        owner = User.objects.get(username=self.username)
        self.upload_path = f'home/{self.username}/uploads/file1.txt'
        folder_path = os.path.dirname(self.upload_path)
        (parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                               owner=owner)
        self.file = ChrisFile(parent_folder=parent_folder, owner=owner)
        self.file.fname.name = self.upload_path
        self.file.save()

    def test_move(self):
        """
        Test whether custom 'move' method successfully updates a ChrisFile with
        the correct path and parent folder.
        """
        new_path =  f'home/{self.username}/tests/file1.txt'

        storage_manager_mock = mock.Mock()
        storage_manager_mock.obj_exists = mock.Mock()
        storage_manager_mock.copy_obj = mock.Mock()
        storage_manager_mock.delete_obj = mock.Mock()

        with mock.patch('core.models.connect_storage') as connect_storage_mock:
            connect_storage_mock.return_value=storage_manager_mock
            self.file.move(new_path)
            storage_manager_mock.obj_exists.assert_called_with(new_path)
            storage_manager_mock.copy_obj.assert_called_with(self.upload_path, new_path)
            self.assertEqual(self.file.fname.name, new_path)
            self.assertEqual(self.file.parent_folder.path, f'home/{self.username}/tests')
            storage_manager_mock.delete_obj.assert_called_with(self.upload_path)
