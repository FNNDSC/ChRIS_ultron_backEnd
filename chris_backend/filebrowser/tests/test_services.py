
import logging
from unittest import mock, skip

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings

from core.models import ChrisFolder
from users.models import UserProxy
from userfiles.models import UserFile
from filebrowser import services


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class ServiceTests(TestCase):
    """
    Test top-level functions in the services module
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        # create users
        self.username = 'foo'
        self.password = 'foopass'
        self.another_username = 'boo'
        self.another_password = 'boopass'

        # create users with their home folders setup
        UserProxy.objects.create_user(username=self.username, password=self.password)
        UserProxy.objects.create_user(username=self.another_username,
                                      password=self.another_password)

    def tearDown(self):
        User.objects.get(username=self.username).delete()
        User.objects.get(username=self.another_username).delete()

        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_get_folder_queryset_folder_does_not_exist(self):
        """
        Test whether the services.get_folder_queryset function returns
        an empty queryset if a folder doesn't exist.
        """
        user = User.objects.get(username=self.username)
        path = f'home/{self.username}/uploads/crazyfolder'
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, user)
        self.assertEqual(qs.count(), 0)

    def test_get_folder_queryset_from_user_for_chris_user(self):
        """
        Test whether the services.get_folder_queryset function
        allows the chris user to see any existing folder.
        """
        chris_user = User.objects.get(username=self.chris_username)
        path = f'home/{self.username}/uploads'
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, chris_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().path, pk_dict['path'])

    def test_get_folder_queryset_from_user_prevent_another_user(self):
        """
        Test whether the services.get_folder_queryset function
        doesn't allow a user to see other user's existing private folders.
        """
        another_user = User.objects.get(username=self.another_username)
        path = f'home/{self.username}/uploads'
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, another_user)
        self.assertEqual(qs.count(), 0)

    def test_get_folder_queryset_top_level_folders(self):
        """
        Test whether the services.get_folder_queryset function
        returns the appropriate queryset for top-level folders for any user.
        """
        chris_user = User.objects.get(username=self.chris_username)
        ChrisFolder.objects.get_or_create(path='PIPELINES', owner=chris_user)
        ChrisFolder.objects.get_or_create(path='SERVICES', owner=chris_user)

        user = User.objects.get(username=self.username)
        another_user = User.objects.get(username=self.another_username)

        for path in ('', 'home', 'PIPELINES', 'SERVICES'):
            pk_dict = {'path': path}
            qs = services.get_folder_queryset(pk_dict, user)
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs.first().path, pk_dict['path'])
            qs = services.get_folder_queryset(pk_dict, another_user)
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs.first().path, pk_dict['path'])

    def test_get_folder_queryset_user_space(self):
        """
        Test whether the services.get_folder_queryset function
        allows the chris user to see any existing folder.
        """
        user = User.objects.get(username=self.username)
        path = f'home/{self.username}'
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().path, pk_dict['path'])
