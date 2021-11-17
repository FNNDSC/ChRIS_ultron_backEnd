
import logging
import io
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status

from core.swiftmanager import SwiftManager
from uploadedfiles.models import UploadedFile


class FileBrowserViewTests(TestCase):
    """
    Generic filebrowser view tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.content_type = 'application/vnd.collection+json'
        self.username = 'test'
        self.password = 'testpass'

        # create a user
        User.objects.create_user(username=self.username, password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class FileBrowserPathListViewTests(FileBrowserViewTests):
    """
    Test the 'filebrowserpath-list' view.
    """

    def setUp(self):
        super(FileBrowserPathListViewTests, self).setUp()
        self.read_url = reverse('filebrowserpath-list')

    def test_filebrowserpath_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'path')
        self.assertEqual(response.data['results'][0]['subfolders'], f'SERVICES,{self.username}')

    def test_filebrowserpath_list_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FileBrowserPathListQuerySearchViewTests(FileBrowserViewTests):
    """
    Test the 'filebrowserpath-list-query-search' view.
    """

    def setUp(self):
        super(FileBrowserPathListQuerySearchViewTests, self).setUp()

        # create a file in the DB "already uploaded" to the server)
        user = User.objects.get(username=self.username)
        upload_path = f'{self.username}/uploads/myfolder/file1.txt'
        uploadedfile = UploadedFile(owner=user)
        uploadedfile.fname.name = upload_path
        uploadedfile.save()
        self.read_url = reverse('filebrowserpath-list-query-search') + f'?path={self.username}/uploads/'

    def test_filebrowserpath_list_query_search_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, f'{self.username}/uploads')
        self.assertIn('myfolder', response.data['results'][0]['subfolders'].split(','))

    def test_filebrowserpath_list_query_search_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FileBrowserPathViewTests(FileBrowserViewTests):
    """
    Test the filebrowserpath view.
    """

    def setUp(self):
        super(FileBrowserPathViewTests, self).setUp()

        # create a file in the DB "already uploaded" to the server)
        user = User.objects.get(username=self.username)
        upload_path = f'{self.username}/uploads/myfolder/file1.txt'
        uploadedfile = UploadedFile(owner=user)
        uploadedfile.fname.name = upload_path
        uploadedfile.save()

        self.read_url = reverse("filebrowserpath", kwargs={"path": f'{self.username}/uploads'})

    def test_filebrowserpath_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, f'{self.username}/uploads')
        self.assertIn('myfolder', response.data['subfolders'].split(','))

    def test_filebrowserpath_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url + 'unknownpath/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserpath_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FileBrowserPathFileListViewTests(FileBrowserViewTests):
    """
    Test the 'filebrowserpath-list' view.
    """

    def setUp(self):
        super(FileBrowserPathFileListViewTests, self).setUp()

        # create a file in the DB "already uploaded" to the server)
        self.swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                          settings.SWIFT_CONNECTION_PARAMS)

        # upload file to Swift storage
        self.upload_path = f'{self.username}/uploads/file2.txt'
        with io.StringIO("test file") as file1:
            self.swift_manager.upload_obj(self.upload_path, file1.read(),
                                         content_type='text/plain')
        user = User.objects.get(username=self.username)
        uploadedfile = UploadedFile(owner=user)
        uploadedfile.fname.name = self.upload_path
        uploadedfile.save()

        self.read_url = reverse("filebrowserpathfile-list",
                                kwargs={"path": f'{self.username}/uploads'})

    def tearDown(self):
        # delete file from Swift storage
        self.swift_manager.delete_obj(self.upload_path)

        super(FileBrowserPathFileListViewTests, self).tearDown()

    def test_filebrowserpathfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'file_resource')
        self.assertContains(response, self.upload_path)

    def test_filebrowserpathfile_list_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url + 'unknownpath/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserpathfile_list_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
