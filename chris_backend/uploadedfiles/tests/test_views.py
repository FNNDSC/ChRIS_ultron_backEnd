
import os, shutil
from unittest import mock, skip

import swiftclient

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from rest_framework import status

from uploadedfiles.models import UploadedFile
from uploadedfiles import views


class UploadedFileViewTests(TestCase):
    """
    Generic uploadedfile view tests' setup and tearDown
    """

    def setUp(self):
        self.content_type = 'application/vnd.collection+json'

        self.chris_username = 'chris'
        self.chris_password = 'chrispass'
        self.username = 'test'
        self.password = 'testpass'

        # create basic models

        # create the chris user and another user
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)
        User.objects.create_user(username=self.username,
                                 password=self.password)

        # create test directory where files are created
        self.test_dir = settings.MEDIA_ROOT + '/test'
        settings.MEDIA_ROOT = self.test_dir
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

    def tearDown(self):
        # remove test directory
        shutil.rmtree(self.test_dir)
        settings.MEDIA_ROOT = os.path.dirname(self.test_dir)


class UploadedFileListViewTests(UploadedFileViewTests):
    """
    Test the uploadedfile-list view
    """

    def setUp(self):
        super(UploadedFileListViewTests, self).setUp()
        user = User.objects.get(username=self.username)
        self.create_read_url = reverse("uploadedfile-list")

        # create a file in the DB "already uploaded" to the server)
        uploadedfile = UploadedFile(upload_path='/file1.txt', owner=user)
        uploadedfile.fname.name = '/test/file1.txt'
        uploadedfile.save()

    @tag('integration')
    def test_integration_uploadedfile_create_success(self):
        # create a test file
        test_file_path = self.test_dir
        self.test_file = test_file_path + '/file2.txt'
        file = open(self.test_file, "w")
        file.write("test file")
        file.close()

        self.client.login(username=self.username, password=self.password)
        # POST request using multipart/form-data to be able to upload file
        with open(self.test_file) as f:
            post = {"fname": f, "upload_path": "/file2.txt"}
            response = self.client.post(self.create_read_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # delete file from Swift storage
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, 'test/uploads/file2.txt')

    def test_uploadedfile_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url,
                                    data={"fname": {}, "upload_path": "/file2.txt"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_uploadedfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "file1.txt")

    def test_uploadedfile_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UploadedFileDetailViewTests(UploadedFileViewTests):
    """
    Test the uploadedfile-detail view
    """

    # def setUp(self):
    #     super(UploadedFileDetailViewTests, self).setUp()
    #     feed = Feed.objects.get(name=self.feedname)
    #     self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})
    #
    #     # create a test file
    #     test_file_path = self.test_dir
    #     self.test_file = test_file_path + '/file1.txt'
    #     file = open(self.test_file, "w")
    #     file.write("test file")
    #     file.close()
    #
    #     # create a file in the DB "already uploaded" to the server
    #     pl_inst = PluginInstance.objects.all()[0]
    #     feedfile = FeedFile(plugin_inst=pl_inst, feed=feed)
    #     feedfile.fname.name = 'file1.txt'
    #     feedfile.save()
    #
    #     self.read_update_delete_url = reverse("feedfile-detail",
    #                                           kwargs={"pk": feedfile.id})


    @skip("test under construction")
    def test_uploadedfile_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "file1.txt")
        self.assertTrue(response.data["feed"].endswith(self.corresponding_feed_url))

    @skip("test under construction")
    def test_uploadedfile_detail_success_user_chris(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "file1.txt")
        self.assertTrue(response.data["feed"].endswith(self.corresponding_feed_url))

    @skip("test under construction")
    def test_uploadedfile_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @skip("test under construction")
    def test_uploadedfile_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(FeedFile.objects.count(), 0)

    @skip("test under construction")
    def test_uploadedfile_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @skip("test under construction")
    def test_uploadedfile_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UploadedFileResourceViewTests(UploadedFileViewTests):
    """
    Test the uploadedfile-resource view
    """
    #
    # def setUp(self):
    #     super(UploadedFileResourceViewTests, self).setUp()
    #     feed = Feed.objects.get(name=self.feedname)
    #     pl_inst = PluginInstance.objects.all()[0]
    #     self.pl_inst = pl_inst
    #     # create a file in the DB "already uploaded" to the server
    #     feedfile = FeedFile(plugin_inst=pl_inst, feed=feed)
    #     feedfile.fname.name = '/tests/file1.txt'
    #     feedfile.save()
    #     self.download_url = reverse("feedfile-resource",
    #                                 kwargs={"pk": feedfile.id}) + 'file1.txt'

        
    @skip("test under construction")
    def test_uploadedfileresource_get(self):
        feedfile = FeedFile.objects.get(fname="/tests/file1.txt")
        fileresource_view_inst = mock.Mock()
        fileresource_view_inst.get_object = mock.Mock(return_value=feedfile)
        request_mock = mock.Mock()
        with mock.patch('feeds.views.Response') as response_mock:
            views.FileResource.get(fileresource_view_inst, request_mock)
            response_mock.assert_called_with(feedfile.fname)

    #@tag('integration')
    @skip("test under construction")
    def test_integration_uploadedfileresource_download_success(self):
        # create a test file
        test_file_path = self.test_dir
        self.test_file = test_file_path + '/file1.txt'
        file = open(self.test_file, "w")
        file.write("test file")
        file.close()

        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # create container in case it doesn't already exist
        conn.put_container(settings.SWIFT_CONTAINER_NAME)

        # upload file to Swift storage
        with open(self.test_file, 'r') as file1:
            conn.put_object(settings.SWIFT_CONTAINER_NAME, '/tests/file1.txt',
                            contents=file1.read(),
                            content_type='text/plain')

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.download_url)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(str(response.content, 'utf-8'), "test file")

        # delete file from Swift storage
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, '/tests/file1.txt')

    @skip("test under construction")
    def test_fileresource_download_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    @skip("test under construction")
    def test_fileresource_download_failure_unauthenticated(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
