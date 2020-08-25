
import logging
import json
import io
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status

from core.swiftmanager import SwiftManager
from uploadedfiles.models import UploadedFile, uploaded_file_path
from uploadedfiles import views


class UploadedFileViewTests(TestCase):
    """
    Generic uploadedfile view tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.content_type = 'application/vnd.collection+json'
        self.chris_username = 'chris'
        self.chris_password = 'chrispass'
        self.username = 'test'
        self.password = 'testpass'
        self.other_username = 'boo'
        self.other_password = 'far'

        # create the chris superuser and two additional users
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        user = User.objects.create_user(username=self.username,
                                 password=self.password)

        # create a file in the DB "already uploaded" to the server)
        self.uploadedfile = UploadedFile(owner=user)
        self.uploadedfile.fname.name = '{}/uploads/file1.txt'.format(user)
        self.uploadedfile.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class UploadedFileListViewTests(UploadedFileViewTests):
    """
    Test the uploadedfile-list view.
    """

    def setUp(self):
        super(UploadedFileListViewTests, self).setUp()
        self.create_read_url = reverse("uploadedfile-list")

    def tearDown(self):
        super(UploadedFileListViewTests, self).tearDown()

    @tag('integration')
    def test_integration_uploadedfile_create_success(self):

        # POST request using multipart/form-data to be able to upload file
        self.client.login(username=self.username, password=self.password)
        upload_path = "{}/uploads/file2.txt".format(self.username)

        with io.StringIO("test file") as f:
            post = {"fname": f, "upload_path": upload_path}
            response = self.client.post(self.create_read_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                     settings.SWIFT_CONNECTION_PARAMS)
        # delete file from Swift storage
        swift_manager.delete_obj(upload_path)

    def test_uploadedfile_create_failure_unauthenticated(self):
        upload_path = "{}/uploads/file2.txt".format(self.username)
        response = self.client.post(self.create_read_url,
                                    data={"fname": {}, "upload_path": upload_path})
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
    Test the uploadedfile-detail view.
    """

    def setUp(self):
        super(UploadedFileDetailViewTests, self).setUp()
        self.read_update_delete_url = reverse("uploadedfile-detail",
                                              kwargs={"pk": self.uploadedfile.id})
        upload_path = "{}/uploads/myfolder/myfile1.txt".format(self.username)
        self.put = json.dumps({
            "template": {"data": [{"name": "upload_path", "value": upload_path}]}})

    def test_uploadedfile_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "file1.txt")

    def test_uploadedfile_detail_success_user_chris(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "file1.txt")

    def test_uploadedfile_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_uploadedfile_update_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_uploadedfile_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_uploadedfile_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        swift_path = self.uploadedfile.fname.name
        mocked_method = 'uploadedfiles.views.SwiftManager.delete_obj'
        with mock.patch(mocked_method) as delete_obj_mock:
            response = self.client.delete(self.read_update_delete_url)
            delete_obj_mock.assert_called_with(swift_path)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertEqual(UploadedFile.objects.count(), 0)

    def test_uploadedfile_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_uploadedfile_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UploadedFileResourceViewTests(UploadedFileViewTests):
    """
    Test the uploadedfile-resource view.
    """

    def setUp(self):
        super(UploadedFileResourceViewTests, self).setUp()
        self.download_url = reverse("uploadedfile-resource",
                                    kwargs={"pk": self.uploadedfile.id}) + 'file1.txt'

    def tearDown(self):
        super(UploadedFileResourceViewTests, self).tearDown()

    def test_uploadedfileresource_get(self):
        uploadedfile = self.uploadedfile
        fileresource_view_inst = mock.Mock()
        fileresource_view_inst.get_object = mock.Mock(return_value=uploadedfile)
        request_mock = mock.Mock()
        with mock.patch('uploadedfiles.views.Response') as response_mock:
            views.UploadedFileResource.get(fileresource_view_inst, request_mock)
            response_mock.assert_called_with(uploadedfile.fname)

    @tag('integration')
    def test_integration_uploadedfileresource_download_success(self):
        swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                     settings.SWIFT_CONNECTION_PARAMS)
        # upload file to Swift storage
        upload_path = "{}/uploads/file1.txt".format(self.username)
        with io.StringIO("test file") as file1:
            swift_manager.upload_file(upload_path, file1.read(), content_type='text/plain')

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.content, 'utf-8'), "test file")

        # delete file from Swift storage
        swift_manager.delete_obj(upload_path)

    def test_fileresource_download_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fileresource_download_failure_unauthenticated(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
