
import logging
from unittest import mock, skip

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings

from core.models import ChrisFolder
from users.models import UserProxy
from filebrowser import services


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class ServiceTests(TestCase):
    """
    Test top-level functions in the services module
    """
    
    # superuser chris (owner of root and top-level folders)
    chris_username = 'chris'
    chris_password = CHRIS_SUPERUSER_PASSWORD

    # normal users
    username = 'fee'
    password = 'feepass'
    other_username = 'bee'
    other_password = 'beepass'
    
    @classmethod
    def setUpClass(cls):
        
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create users with their home folders setup
        UserProxy.objects.create_user(username=cls.username, password=cls.password)
        UserProxy.objects.create_user(username=cls.other_username, 
                                      password=cls.other_password)

    @classmethod
    def tearDownClass(cls):
        User.objects.get(username=cls.username).delete()
        User.objects.get(username=cls.other_username).delete()

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

    def test_get_folder_queryset_from_user_success_for_chris_user(self):
        """
        Test whether the services.get_folder_queryset function
        allows the chris superuser to see any existing folder.
        """
        chris_user = User.objects.get(username=self.chris_username)
        path = f'home/{self.username}/uploads'
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, chris_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().path, pk_dict['path'])

    def test_get_folder_queryset_from_user_failure_other_user(self):
        """
        Test whether the services.get_folder_queryset function
        doesn't allow a user to see other user's existing private folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}/uploads'
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, other_user)
        self.assertEqual(qs.count(), 0)

    def test_get_folder_queryset_from_user_public_success_other_user(self):
        """
        Test whether the services.get_folder_queryset function
        allows a user to see other user's existing public folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_public_access()
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, other_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().path, pk_dict['path'])
        folder.remove_public_access()

    def test_get_folder_queryset_from_user_shared_success_other_user(self):
        """
        Test whether the services.get_folder_queryset function
        allows a user to see other user's existing shared folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_user_permission(other_user, 'r')
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, other_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().path, pk_dict['path'])
        folder.remove_user_permission(other_user, 'r')

    def test_get_folder_queryset_from_user_shared_group_success_other_user(self):
        """
        Test whether the services.get_folder_queryset function
        allows a user to see other user's existing shared folders with its group.
        """
        other_user = User.objects.get(username=self.other_username)
        other_user_group = other_user.groups.first()
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_group_permission(other_user_group, 'r')
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, other_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().path, pk_dict['path'])
        folder.remove_group_permission(other_user_group, 'r')

    def test_get_folder_queryset_top_level_folders(self):
        """
        Test whether the services.get_folder_queryset function returns the
        appropriate queryset for top-level folders for any authenticated user.
        """
        user = User.objects.get(username=self.username)
        other_user = User.objects.get(username=self.other_username)

        for path in ('', 'home', 'PIPELINES', 'SERVICES', 'PUBLIC', 'SHARED'):
            pk_dict = {'path': path}
            qs = services.get_folder_queryset(pk_dict, user)
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs.first().path, pk_dict['path'])
            qs = services.get_folder_queryset(pk_dict, other_user)
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs.first().path, pk_dict['path'])

    def test_get_folder_queryset_top_level_folders_unauthenticated(self):
        """
        Test whether the services.get_folder_queryset function returns the
        appropriate queryset for top-level folders for unauthenticated users.
        """
        for path in ('', 'PIPELINES', 'PUBLIC'):
            pk_dict = {'path': path}
            qs = services.get_folder_queryset(pk_dict)
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs.first().path, pk_dict['path'])

    def test_get_folder_queryset_user_space(self):
        """
        Test whether the services.get_folder_queryset function
        allows users to see any existing folder owned by them.
        """
        user = User.objects.get(username=self.username)
        path = f'home/{self.username}'
        pk_dict = {'path': path}
        qs = services.get_folder_queryset(pk_dict, user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().path, pk_dict['path'])

    def test_get_folder_children_queryset_from_user_success_for_chris_user(self):
        """
        Test whether the services.get_folder_children_queryset function
        allows the chris superuser to see all the child folders of any existing folder.
        """
        chris_user = User.objects.get(username=self.chris_username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_children_queryset(folder, chris_user)
        self.assertEqual(qs.count(), 2)
        self.assertIn(f'{path}/uploads', [f.path for f in qs.all()])
        self.assertIn(f'{path}/feeds', [f.path for f in qs.all()])

    def test_get_folder_children_queryset_from_user_failure_other_user(self):
        """
        Test whether the services.get_folder_children_queryset function
        doesn't allow a user to see the private child folders of other user's
        existing private folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_children_queryset(folder, other_user)
        self.assertEqual(qs.count(), 0)

    def test_get_folder_children_queryset_from_user_public_success_other_user(self):
        """
        Test whether the services.get_folder_children_queryset function
        allows a user to see the child folders of other user's existing public folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_public_access()
        qs = services.get_folder_children_queryset(folder, other_user)
        self.assertEqual(qs.count(), 2)
        self.assertIn(f'{path}/uploads', [f.path for f in qs.all()])
        self.assertIn(f'{path}/feeds', [f.path for f in qs.all()])
        folder.remove_public_access()

    def test_get_folder_children_queryset_from_user_shared_success_other_user(self):
        """
        Test whether the services.get_folder_children_queryset function
        allows a user to see the child folders of other user's existing shared folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_user_permission(other_user, 'r')
        qs = services.get_folder_children_queryset(folder, other_user)
        self.assertEqual(qs.count(), 2)
        self.assertIn(f'{path}/uploads', [f.path for f in qs.all()])
        self.assertIn(f'{path}/feeds', [f.path for f in qs.all()])
        folder.remove_user_permission(other_user, 'r')

    def test_get_folder_children_queryset_from_user_shared_group_success_other_user(self):
        """
        Test whether the services.get_folder_children_queryset function
        allows a user to see the child folders of other user's existing folders
        shared with its group.
        """
        other_user = User.objects.get(username=self.other_username)
        other_user_group = other_user.groups.first()
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_group_permission(other_user_group, 'r')
        qs = services.get_folder_children_queryset(folder, other_user)
        self.assertEqual(qs.count(), 2)
        paths = [f.path for f in qs.all()]
        self.assertIn(f'{path}/uploads', paths)
        self.assertIn(f'{path}/feeds', paths)
        folder.remove_group_permission(other_user_group, 'r')

    def test_get_folder_children_queryset_top_level_folders(self):
        """
        Test whether the services.get_folder_children_queryset function returns the
        appropriate queryset for top-level folders for any authenticated user.
        """
        user = User.objects.get(username=self.username)

        folder = ChrisFolder.objects.get(path='')
        qs = services.get_folder_children_queryset(folder, user)
        self.assertEqual(qs.count(), 5)
        paths = [f.path for f in qs.all()]

        for path in ('home', 'PIPELINES', 'SERVICES', 'PUBLIC', 'SHARED'):
            self.assertIn(path, paths)

    def test_get_folder_children_queryset_top_level_folders_unauthenticated(self):
        """
        Test whether the services.get_folder_children_queryset function returns the
        appropriate queryset for top-level folders for unauthenticated users.
        """
        folder = ChrisFolder.objects.get(path='')
        qs = services.get_folder_children_queryset(folder)
        self.assertEqual(qs.count(), 2)
        paths = [f.path for f in qs.all()]

        for path in ('PIPELINES', 'PUBLIC'):
            self.assertIn(path, paths)

    def test_get_folder_children_queryset_user_space(self):
        """
        Test whether the services.get_folder_children_queryset function
        allows users to see any existing folder owned by them.
        """
        user = User.objects.get(username=self.username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_children_queryset(folder, user)
        self.assertEqual(qs.count(), 2)
        paths = [f.path for f in qs.all()]
        self.assertIn(f'{path}/uploads', paths)
        self.assertIn(f'{path}/feeds', paths)


    def test_get_folder_files_queryset_from_user_success_for_chris_user(self):
        """
        Test whether the services.get_folder_files_queryset function
        allows the chris superuser to see all the child files of any existing folder.
        """
        chris_user = User.objects.get(username=self.chris_username)
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_files_queryset(folder, chris_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(f'{path}/welcome.txt', qs.first().fname.name)

    def test_get_folder_files_queryset_from_user_failure_other_user(self):
        """
        Test whether the services.get_folder_files_queryset function
        doesn't allow a user to see the private child files of other user's
        existing private folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_files_queryset(folder, other_user)
        self.assertEqual(qs.count(), 0)

    def test_get_folder_files_queryset_from_user_public_success_other_user(self):
        """
        Test whether the services.get_folder_files_queryset function
        allows a user to see the child files of other user's existing public folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_public_access()
        qs = services.get_folder_files_queryset(folder, other_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(f'{path}/welcome.txt', qs.first().fname.name)
        folder.remove_public_access()

    def test_get_folder_files_queryset_from_user_shared_success_other_user(self):
        """
        Test whether the services.get_folder_files_queryset function
        allows a user to see the child files of other user's existing shared folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_user_permission(other_user, 'r')
        qs = services.get_folder_files_queryset(folder, other_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(f'{path}/welcome.txt', qs.first().fname.name)
        folder.remove_user_permission(other_user, 'r')

    def test_get_folder_files_queryset_from_user_shared_group_success_other_user(self):
        """
        Test whether the services.get_folder_files_queryset function
        allows a user to see the child files of other user's existing folders
        shared with its group.
        """
        other_user = User.objects.get(username=self.other_username)
        other_user_group = other_user.groups.first()
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_group_permission(other_user_group, 'r')
        qs = services.get_folder_files_queryset(folder, other_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(f'{path}/welcome.txt', qs.first().fname.name)
        folder.remove_group_permission(other_user_group, 'r')

    def test_get_folder_files_queryset_user_space(self):
        """
        Test whether the services.get_folder_files_queryset function
        allows users to see any existing folder's files owned by them.
        """
        user = User.objects.get(username=self.username)
        path = f'home/{self.username}/uploads'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_files_queryset(folder, user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(f'{path}/welcome.txt', qs.first().fname.name)


    def test_get_folder_link_files_queryset_from_user_success_for_chris_user(self):
        """
        Test whether the services.get_folder_link_files_queryset function
        allows the chris superuser to see all the child link files of any existing folder.
        """
        chris_user = User.objects.get(username=self.chris_username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_link_files_queryset(folder, chris_user)
        self.assertEqual(qs.count(), 2)
        paths = [lf.fname.name for lf in qs.all()]
        self.assertIn(f'{path}/public.chrislink', paths)
        self.assertIn(f'{path}/shared.chrislink', paths)

    def test_get_folder_link_files_queryset_from_user_failure_other_user(self):
        """
        Test whether the services.get_folder_link_files_queryset function
        doesn't allow a user to see the private child link files of other user's
        existing private folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_link_files_queryset(folder, other_user)
        self.assertEqual(qs.count(), 0)

    def test_get_folder_link_files_queryset_from_user_public_success_other_user(self):
        """
        Test whether the services.get_folder_link_files_queryset function
        allows a user to see the child link files of other user's existing public folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_public_access()
        qs = services.get_folder_link_files_queryset(folder, other_user)
        self.assertEqual(qs.count(), 2)
        paths = [lf.fname.name for lf in qs.all()]
        self.assertIn(f'{path}/public.chrislink', paths)
        self.assertIn(f'{path}/shared.chrislink', paths)
        folder.remove_public_access()

    def test_get_folder_link_files_queryset_from_user_shared_success_other_user(self):
        """
        Test whether the services.get_folder_link_files_queryset function
        allows a user to see the child link files of other user's existing shared folders.
        """
        other_user = User.objects.get(username=self.other_username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_user_permission(other_user, 'r')
        qs = services.get_folder_link_files_queryset(folder, other_user)
        self.assertEqual(qs.count(), 2)
        paths = [lf.fname.name for lf in qs.all()]
        self.assertIn(f'{path}/public.chrislink', paths)
        self.assertIn(f'{path}/shared.chrislink', paths)
        folder.remove_user_permission(other_user, 'r')

    def test_get_folder_link_files_queryset_from_user_shared_group_success_other_user(self):
        """
        Test whether the services.get_folder_link_files_queryset function
        allows a user to see the child link files of other user's existing folders
        shared with its group.
        """
        other_user = User.objects.get(username=self.other_username)
        other_user_group = other_user.groups.first()
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        folder.grant_group_permission(other_user_group, 'r')
        qs = services.get_folder_link_files_queryset(folder, other_user)
        self.assertEqual(qs.count(), 2)
        paths = [lf.fname.name for lf in qs.all()]
        self.assertIn(f'{path}/public.chrislink', paths)
        self.assertIn(f'{path}/shared.chrislink', paths)
        folder.remove_group_permission(other_user_group, 'r')

    def test_get_folder_link_files_queryset_user_space(self):
        """
        Test whether the services.get_folder_link_files_queryset function
        allows users to see any existing folder's link files owned by them.
        """
        user = User.objects.get(username=self.username)
        path = f'home/{self.username}'
        folder = ChrisFolder.objects.get(path=path)
        qs = services.get_folder_link_files_queryset(folder, user)
        self.assertEqual(qs.count(), 2)
        paths = [lf.fname.name for lf in qs.all()]
        self.assertIn(f'{path}/public.chrislink', paths)
        self.assertIn(f'{path}/shared.chrislink', paths)
