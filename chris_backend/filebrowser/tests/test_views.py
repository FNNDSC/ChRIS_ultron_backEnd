
import logging
import io
import os
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status

from core.models import ChrisFolder
from core.storage import connect_storage
from userfiles.models import UserFile
from plugins.models import PluginMeta, Plugin, ComputeResource
from plugininstances.models import PluginInstance


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class FileBrowserViewTests(TestCase):
    """
    Generic filebrowser view tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = 'chris1234'
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)

        self.content_type = 'application/vnd.collection+json'
        self.username = 'test'
        self.password = 'testpass'
        self.other_username = 'booo'
        self.other_password = 'booopass'

        # create user and its home folder
        user = User.objects.create_user(username=self.username, password=self.password)
        ChrisFolder.objects.get_or_create(path=f'home/{self.username}', owner=user)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class FileBrowserFolderListViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-list' view.
    """

    def setUp(self):
        super(FileBrowserFolderListViewTests, self).setUp()
        self.read_url = reverse('chrisfolder-list')

    def test_filebrowserfolder_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'path')
        #import pdb; pdb.set_trace()
        self.assertEqual(response.data['results'][0]['path'],'')


class FileBrowserFolderListQuerySearchViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-list-query-search' view.
    """

    def setUp(self):
        super(FileBrowserFolderListQuerySearchViewTests, self).setUp()

        self.read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.username}'

    def test_filebrowserfolder_list_query_search_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, f'home/{self.username}')


class FileBrowserFolderDetailViewTests(FileBrowserViewTests):
    """
    Test the chrisfolder-detail view.
    """

    def setUp(self):
        super(FileBrowserFolderDetailViewTests, self).setUp()

        # create a file in the DB "already uploaded" to the server)
        user = User.objects.get(username=self.username)
        upload_path = f'home/{self.username}/uploads/myfolder/file1.txt'

        folder_path = os.path.dirname(upload_path)
        (file_parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                    owner=user)
        userfile = UserFile(owner=user, parent_folder=file_parent_folder)
        userfile.fname.name = upload_path
        userfile.save()

        self.read_url = reverse("chrisfolder-detail", kwargs={"pk": file_parent_folder.id})

    def test_filebrowserfolder_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, f'home/{self.username}/uploads/myfolder')

    def test_filebrowserfolder_success_shared_feed(self):
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
        read_url = reverse("chrisfolder-detail", kwargs={"pk": pl_inst.output_folder.id})
        response = self.client.get(read_url)
        #import pdb;pdb.set_trace()
        self.assertContains(response, f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}/')

    def test_filebrowserfolder_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("chrisfolder-detail", kwargs={"pk": 111111111}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolder_failure__not_found_unauthenticated_user(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FileBrowserFolderChildListViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-child-list' view.
    """

    def setUp(self):
        super(FileBrowserFolderChildListViewTests, self).setUp()

        folder = ChrisFolder.objects.get(path=f'home')
        self.read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})

    def test_filebrowserfolderfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, f'home/{self.username}')

    def test_filebrowserfolderfile_list_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("chrisfolder-child-list", kwargs={"pk": 111111111}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FileBrowserFolderFileListViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-file-list' view.
    """

    def setUp(self):
        super(FileBrowserFolderFileListViewTests, self).setUp()

        # create a file in the DB "already uploaded" to the server)
        self.storage_manager = connect_storage(settings)
        # upload file to storage
        self.upload_path = f'home/{self.username}/uploads/file2.txt'
        with io.StringIO("test file") as file1:
            self.storage_manager.upload_obj(self.upload_path, file1.read(),
                                         content_type='text/plain')
        user = User.objects.get(username=self.username)

        folder_path = os.path.dirname(self.upload_path)
        (file_parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                    owner=user)
        userfile = UserFile(owner=user, parent_folder=file_parent_folder)
        userfile.fname.name = self.upload_path
        userfile.save()

        self.read_url = reverse("chrisfolder-file-list", kwargs={"pk": file_parent_folder.id})

    def tearDown(self):
        # delete file from storage
        self.storage_manager.delete_obj(self.upload_path)

        super(FileBrowserFolderFileListViewTests, self).tearDown()

    def test_filebrowserfolderfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'file_resource')
        self.assertContains(response, self.upload_path)

    def test_filebrowserfolderfile_list_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("chrisfolder-file-list", kwargs={"pk": 111111111}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
