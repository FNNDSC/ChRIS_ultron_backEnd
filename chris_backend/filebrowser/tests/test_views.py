
import logging
import io
import json
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status

from core.storage import connect_storage
from uploadedfiles.models import UploadedFile
from plugins.models import PluginMeta, Plugin, ComputeResource
from plugininstances.models import PluginInstance, PluginInstanceFile


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


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
        self.other_username = 'booo'
        self.other_password = 'booopass'

        # create user
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
        self.assertEqual(json.loads(response.data['results'][0]['subfolders']),
                         sorted(['PIPELINES', 'SERVICES', self.username]))

    def test_filebrowserpath_list_success_shared_feed(self):
        user = User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        # create compute resource
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create 'fs' plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([compute_resource])
        plugin.save()

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user, title='test',
                                                compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertEqual(json.loads(response.data['results'][0]['subfolders']),
                         sorted(['PIPELINES', 'SERVICES', self.username,
                                 self.other_username]))


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
        self.assertIn('myfolder', json.loads(response.data['results'][0]['subfolders']))


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
        self.assertIn('myfolder', json.loads(response.data['subfolders']))

    def test_filebrowserpath_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url + 'unknownpath/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserpath_failure__not_found_unauthenticated_user(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FileBrowserPathFileListViewTests(FileBrowserViewTests):
    """
    Test the 'filebrowserpath-list' view.
    """

    def setUp(self):
        super(FileBrowserPathFileListViewTests, self).setUp()

        # create a file in the DB "already uploaded" to the server)
        self.storage_manager = connect_storage(settings)
        # upload file to storage
        self.upload_path = f'{self.username}/uploads/file2.txt'
        with io.StringIO("test file") as file1:
            self.storage_manager.upload_obj(self.upload_path, file1.read(),
                                         content_type='text/plain')
        user = User.objects.get(username=self.username)
        uploadedfile = UploadedFile(owner=user)
        uploadedfile.fname.name = self.upload_path
        uploadedfile.save()

        self.read_url = reverse("filebrowserpathfile-list",
                                kwargs={"path": f'{self.username}/uploads'})

    def tearDown(self):
        # delete file from storage
        self.storage_manager.delete_obj(self.upload_path)

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
