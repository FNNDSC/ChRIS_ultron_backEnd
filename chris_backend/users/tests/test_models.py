
import logging
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings

from core.models import ChrisFolder
from core.storage.helpers import mock_storage
from userfiles.models import UserFile
from users.models import UserProxy


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL
CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.username = 'foo'
        self.password = 'foo-pass'
        self.email = 'foo@gmail.com'

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class UserProxyModelTests(ModelTests):

    def test_save_assigns_predefined_groups_first_time_user_is_saved(self):
        """
        Test whether overriden save method assigns predefined groups to the user the
        first time the user is saved.
        """
        with mock_storage('users.models.settings') as storage_manager:
            # create user
            user = UserProxy.objects.create_user(username=self.username,
                                                 password=self.password)

            user_grp_names = [g.name for g in user.groups.all()]
            self.assertEqual(len(user_grp_names), 2)
            self.assertIn('all_users', user_grp_names)
            self.assertIn('pacs_users', user_grp_names)

            user.save()

            user_grp_names = [g.name for g in user.groups.all()]
            self.assertEqual(len(user_grp_names), 2)
            self.assertIn('all_users', user_grp_names)
            self.assertIn('pacs_users', user_grp_names)

    def test_save_creates_predefined_folders_under_home_first_time_user_is_saved(self):
        """
        Test whether overriden save method creates predefined folders under the
        user's home directory the first time the user is saved.
        """
        with mock_storage('users.models.settings') as storage_manager:
            # create user
            user = UserProxy.objects.create_user(username=self.username,
                                                 password=self.password)

            home_folder = ChrisFolder.objects.get(path=f'home/{self.username}')
            subfolder_paths = [folder.path for folder in home_folder.children.all()]
            self.assertEqual(len(subfolder_paths), 2)
            self.assertIn(f'home/{self.username}/feeds', subfolder_paths)
            self.assertIn(f'home/{self.username}/uploads', subfolder_paths)

            user.save()

            home_folder.refresh_from_db()
            subfolder_paths = [folder.path for folder in home_folder.children.all()]
            self.assertEqual(len(subfolder_paths), 2)
            self.assertIn(f'home/{self.username}/feeds', subfolder_paths)
            self.assertIn(f'home/{self.username}/uploads', subfolder_paths)

    def test_save_creates_predefined_link_files_under_home_first_time_user_is_saved(self):
        """
        Test whether overriden save method creates predefined link files under the
        user's home directory the first time the user is saved.
        """
        with mock_storage('users.models.settings') as storage_manager:
            # create user
            user = UserProxy.objects.create_user(username=self.username,
                                                 password=self.password)

            home_folder = ChrisFolder.objects.get(path=f'home/{self.username}')
            lf_paths = [lf.fname.name for lf in home_folder.chris_link_files.all()]
            lf_pointed_paths = [lf.path for lf in home_folder.chris_link_files.all()]
            self.assertEqual(len(lf_paths), 2)
            self.assertIn(f'home/{self.username}/public.chrislink', lf_paths)
            self.assertIn('PUBLIC', lf_pointed_paths)
            self.assertIn(f'home/{self.username}/shared.chrislink', lf_paths)
            self.assertIn('SHARED', lf_pointed_paths)

            user.save()

            home_folder.refresh_from_db()
            lf_paths = [lf.fname.name for lf in home_folder.chris_link_files.all()]
            lf_pointed_paths = [lf.path for lf in home_folder.chris_link_files.all()]
            self.assertEqual(len(lf_paths), 2)
            self.assertIn(f'home/{self.username}/public.chrislink', lf_paths)
            self.assertIn('PUBLIC', lf_pointed_paths)
            self.assertIn(f'home/{self.username}/shared.chrislink', lf_paths)
            self.assertIn('SHARED', lf_pointed_paths)

    def test_save_creates_welcome_file_under_home_uploads_first_time_user_is_saved(self):
        """
        Test whether overriden save method creates a welcome.txt under the
        user's uploads directory the first time the user is saved.
        """
        with mock_storage('users.models.settings') as storage_manager:
                # create user
                user = UserProxy.objects.create_user(username=self.username,
                                                     password=self.password)

                welcome_file_path = f'home/{self.username}/uploads/welcome.txt'
                welcome_file = UserFile.objects.get(owner=user)
                self.assertEqual(welcome_file.fname.name, welcome_file_path)
                self.assertTrue(storage_manager.obj_exists(welcome_file_path))

                user.save()

                welcome_file = UserFile.objects.get(owner=user)
                self.assertEqual(welcome_file.fname.name, welcome_file_path)
                self.assertTrue(storage_manager.obj_exists(welcome_file_path))
