
import logging
import json
import io
from unittest import mock

import swiftclient

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status

from pacsfiles.models import PACS, PACSFile
from pacsfiles import views


class PACSFileViewTests(TestCase):
    """
    Generic pacsfile view tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.content_type = 'application/vnd.collection+json'
        self.username = 'test'
        self.password = 'testpass'

        User.objects.create_user(username=self.username, password=self.password)

        # create a PACS file in the DB "already registered" to the server)
        pacs = PACS(identifier='MyPACS')
        pacs.save()
        pacs_file = PACSFile(PatientID='123456',
                             PatientName='crazy',
                             StudyInstanceUID='1.1.3432.54.6545674765.765434',
                             StudyDescription='brain_crazy_study',
                             SeriesInstanceUID='2.4.3432.54.845674765.763345',
                             SeriesDescription='SAG T1 MPRAGE',
                             pacs=pacs)
        self.path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file1.dcm'
        pacs_file.fname.name = self.path
        pacs_file.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PACSFileListViewTests(PACSFileViewTests):
    """
    Test the pacsfile-list view.
    """

    def setUp(self):
        super(PACSFileListViewTests, self).setUp()
        self.create_read_url = reverse("pacsfile-list")
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file2.dcm'
        self.post = json.dumps(
            {"template": {"data": [{"name": "path", "value": path},
                                   {"name": "PatientID", "value": "123456"},
                                   {"name": "PatientName", "value": "crazy"},
                                   {"name": "StudyInstanceUID",
                                    "value": '1.1.3432.54.6545674765.765434'},
                                   {"name": "StudyDescription", "value": "brain_crazy_study"},
                                   {"name": "SeriesInstanceUID",
                                    "value": "2.4.3432.54.845674765.763345"},
                                   {"name": "SeriesDescription", "value": "SAG T1 MPRAGE"},
                                   {"name": "pacs_name", "value": "MyPACS"}]}})

    def tearDown(self):
        super(PACSFileListViewTests, self).tearDown()

    @tag('integration')
    def test_integration_pacsfile_create_success(self):
        chris_username = 'chris'
        chris_password = 'chris1234'
        User.objects.create_user(username=chris_username, password=chris_password)

        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file2.dcm'

        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # create container in case it doesn't already exist
        conn.put_container(settings.SWIFT_CONTAINER_NAME
                           )
        # upload file to Swift storage
        with io.StringIO("test file") as file1:
            conn.put_object(settings.SWIFT_CONTAINER_NAME, path,
                            contents=file1.read(),
                            content_type='text/plain')
        # make the POST request using the chris user
        self.client.login(username=chris_username, password=chris_password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # delete file from Swift storage
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, path)

    def test_pacsfile_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pacsfile_create_failure_already_exists(self):
        chris_username = 'chris'
        chris_password = 'chris1234'
        User.objects.create_user(username=chris_username, password=chris_password)
        self.client.login(username=chris_username, password=chris_password)
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file2.dcm'
        pacs = PACS.objects.get(identifier='MyPACS')
        pacs_file = PACSFile(PatientID='123456',
                             StudyInstanceUID='1.1.3432.54.6545674765.765434',
                             SeriesInstanceUID='2.4.3432.54.845674765.763345',
                             pacs=pacs)
        pacs_file.fname.name = path
        pacs_file.save()
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pacsfile_create_failure_permission_denied_not_chris_user(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pacsfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, self.path)

    def test_pacsfile_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PACSFileDetailViewTests(PACSFileViewTests):
    """
    Test the pacsfile-detail view.
    """

    def setUp(self):
        super(PACSFileDetailViewTests, self).setUp()
        pacs_file = PACSFile.objects.get(PatientID=123456)
        self.read_url = reverse("pacsfile-detail",
                                kwargs={"pk": pacs_file.id})

    def test_pacsfile_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, self.path)

    def test_pacsfile_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PACSFileResourceViewTests(PACSFileViewTests):
    """
    Test the pacsfile-resource view.
    """

    def setUp(self):
        super(PACSFileResourceViewTests, self).setUp()
        pacs_file = PACSFile.objects.get(PatientID=123456)
        self.download_url = reverse("pacsfile-resource",
                                    kwargs={"pk": pacs_file.id}) + 'file1.dcm'

    def tearDown(self):
        super(PACSFileResourceViewTests, self).tearDown()

    def test_pacsfileresource_get(self):
        pacs_file = PACSFile.objects.get(PatientID=123456)
        fileresource_view_inst = mock.Mock()
        fileresource_view_inst.get_object = mock.Mock(return_value=pacs_file)
        request_mock = mock.Mock()
        with mock.patch('pacsfiles.views.Response') as response_mock:
            views.PACSFileResource.get(fileresource_view_inst, request_mock)
            response_mock.assert_called_with(pacs_file.fname)

    @tag('integration')
    def test_integration_pacsfileresource_download_success(self):
        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # create container in case it doesn't already exist
        conn.put_container(settings.SWIFT_CONTAINER_NAME
                           )
        # upload file to Swift storage
        with io.StringIO("test file") as file1:
            conn.put_object(settings.SWIFT_CONTAINER_NAME, self.path,
                            contents=file1.read(),
                            content_type='text/plain')

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.content, 'utf-8'), "test file")

        # delete file from Swift storage
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, self.path)

    def test_fileresource_download_failure_unauthenticated(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
