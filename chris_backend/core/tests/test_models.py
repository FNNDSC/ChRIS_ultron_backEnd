
import io
import logging
import os
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User

from core.models import (ChrisFolder, ChrisFile, ChrisLinkFile, PathAccessError,
                         validate_path_access, user_can_access_obj)
from core.storage import connect_storage
from userfiles.models import UserFile


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


class ChrisFolderModelTests(ModelTests):

    def setUp(self):
        super(ChrisFolderModelTests, self).setUp()

    def test_get_first_existing_folder_ancestor(self):
        """
        Test whether custom get_first_existing_folder_ancestor method returns the
        closest ancestor folder (by path prefix including the passed path itself) that
        exists in the DB.
        """
        folder = ChrisFolder.get_first_existing_folder_ancestor('')
        self.assertEqual(folder.path, '')
        folder = ChrisFolder.get_first_existing_folder_ancestor('home')
        self.assertEqual(folder.path, 'home')
        folder = ChrisFolder.get_first_existing_folder_ancestor('home/12345678/999999')
        self.assertEqual(folder.path, 'home')
        folder = ChrisFolder.get_first_existing_folder_ancestor('home/12345678/file.txt')
        self.assertEqual(folder.path, 'home')


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


class UserCanAccessObjTests(ModelTests):
    """
    Tests for the canonical ``user_can_access_obj`` read-access rule.
    """

    def test_owner_chris_public_and_permission_rule(self):
        """
        Test the owner/superuser/public/permission read-access rule.
        """
        user = User.objects.get(username=self.username)
        chris = User.objects.get(username='chris')
        other = User.objects.create_user(username='other3', password='o-pass')

        folder, _ = ChrisFolder.objects.get_or_create(
            path='home/other3/uploads', owner=other)

        # owner -> allowed
        self.assertTrue(user_can_access_obj(folder, other))
        # superuser 'chris' -> allowed
        self.assertTrue(user_can_access_obj(folder, chris))
        # unrelated user, not public, no permission -> denied
        self.assertFalse(user_can_access_obj(folder, user))

        # public -> allowed
        folder.public = True
        folder.save()
        self.assertTrue(user_can_access_obj(folder, user))

        # explicitly shared with the user -> allowed
        folder.public = False
        folder.save()
        folder.grant_user_permission(user, 'r')
        self.assertTrue(user_can_access_obj(folder, user))


class ValidatePathAccessTests(ModelTests):
    """
    Tests for the centralized ``validate_path_access`` path-access
    authorization function.
    """

    def test_rejects_structural_paths_with_exact_messages(self):
        """
        Test whether validate_path_access rejects structurally invalid paths and
        that the exact, distinct error messages are preserved.
        """
        user = User.objects.get(username=self.username)

        cases = [
            ('home',
             "This field may not reference a top-level folder path 'home'."),
            ('NOTAROOT/x',
             "This field may not reference an invalid path 'NOTAROOT/x'."),
            (f'home/{self.username}',
             f"This field may not reference a home folder path "
             f"'home/{self.username}'."),
            (f'home/{self.username}/feeds',
             f"This field may not reference a home's feeds folder path "
             f"'home/{self.username}/feeds'."),
        ]
        for path, expected_msg in cases:
            with self.assertRaises(PathAccessError) as cm:
                validate_path_access(user, path)
            self.assertEqual(str(cm.exception), expected_msg)

    def test_rejects_nonexistent_path_with_exact_message(self):
        """
        Test whether validate_path_access rejects a structurally valid path that
        does not resolve to any folder/file/link file.
        """
        user = User.objects.get(username=self.username)
        with self.assertRaises(PathAccessError) as cm:
            validate_path_access(user, 'home/someone/uploads')
        self.assertEqual(
            str(cm.exception),
            "This field may not reference an invalid path 'home/someone/uploads'.")

    def test_folder_owner_public_and_permission_rule(self):
        """
        Test the owner/public/permission access rule and that a normalized path
        is returned on success.
        """
        user = User.objects.get(username=self.username)
        own_folder, _ = ChrisFolder.objects.get_or_create(
            path=f'home/{self.username}/uploads', owner=user)

        # owner -> allowed; trailing slash is normalized away in the return value
        self.assertEqual(validate_path_access(user, own_folder.path + '/'),
                         own_folder.path)

        other = User.objects.create_user(username='other', password='other-pass')
        other_folder, _ = ChrisFolder.objects.get_or_create(
            path='home/other/uploads', owner=other)

        # not owner / not public / no permission -> denied (permission message)
        with self.assertRaises(PathAccessError) as cm:
            validate_path_access(user, other_folder.path)
        self.assertEqual(
            str(cm.exception),
            "User does not have permission to access path 'home/other/uploads'.")

        # public -> allowed
        other_folder.public = True
        other_folder.save()
        self.assertEqual(validate_path_access(user, other_folder.path),
                         other_folder.path)

        # explicitly shared with the user -> allowed
        other_folder.public = False
        other_folder.save()
        other_folder.grant_user_permission(user, 'r')
        self.assertEqual(validate_path_access(user, other_folder.path),
                         other_folder.path)

    def test_chris_superuser_bypass(self):
        """
        Test whether the 'chris' superuser is allowed to access any path.
        """
        chris = User.objects.get(username='chris')
        other = User.objects.create_user(username='other2', password='o-pass')
        other_folder, _ = ChrisFolder.objects.get_or_create(
            path='home/other2/uploads', owner=other)
        self.assertEqual(validate_path_access(chris, other_folder.path),
                         other_folder.path)


@tag('integration')
class ValidatePathAccessStorageTests(ModelTests):
    """
    Storage-backed tests for ``validate_path_access`` covering the ChrisFile and
    ChrisLinkFile resolution branches and the PUBLIC/SHARED link-target rule.
    """

    def setUp(self):
        super(ValidatePathAccessStorageTests, self).setUp()
        self.storage_manager = connect_storage(settings)

    def test_resolves_file_and_link_targets(self):
        user = User.objects.get(username=self.username)
        folder, _ = ChrisFolder.objects.get_or_create(
            path=f'home/{self.username}/uploads', owner=user)

        # ChrisFile branch -> owned by user -> allowed
        fpath = f'home/{self.username}/uploads/f.txt'
        with io.StringIO('x') as f:
            self.storage_manager.upload_obj(fpath, f.read(),
                                            content_type='text/plain')
        uf = UserFile(owner=user, parent_folder=folder)
        uf.fname.name = fpath
        uf.save()
        self.assertEqual(validate_path_access(user, fpath), fpath)

        # ChrisLinkFile branch, target not PUBLIC/SHARED -> allowed
        lf = ChrisLinkFile(path=f'home/{self.username}/uploads', owner=user,
                           parent_folder=folder)
        lf.save(name='mylink')
        self.assertEqual(validate_path_access(user, lf.fname.name),
                         lf.fname.name)

        # ChrisLinkFile whose target is PUBLIC -> rejected even though owned
        lf2 = ChrisLinkFile(path='PUBLIC', owner=user, parent_folder=folder)
        lf2.save(name='publink')
        with self.assertRaises(PathAccessError) as cm:
            validate_path_access(user, lf2.fname.name)
        self.assertEqual(
            str(cm.exception),
            f"This field may not reference an invalid path '{lf2.fname.name}'.")

        # delete files from storage
        self.storage_manager.delete_path(f'home/{self.username}/uploads')
