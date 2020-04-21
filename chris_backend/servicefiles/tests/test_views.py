
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

from servicefiles.models import Service, ServiceFile
from servicefiles import views


class ServiceFileViewTests(TestCase):
    """
    Generic servicefile view tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.content_type = 'application/vnd.collection+json'
        self.username = 'test'
        self.password = 'testpass'

        User.objects.create_user(username=self.username, password=self.password)

        # create a pacs file in the DB "already registered" to the server)
        service = Service(identifier='MyService')
        service.save()

        self.path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file1.dcm'
        service_file = ServiceFile(service=service)
        service_file.fname.name = self.path
        service_file.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class ServiceFileListViewTests(ServiceFileViewTests):
    """
    Test the servicefile-list view.
    """

    def setUp(self):
        super(ServiceFileListViewTests, self).setUp()
        self.create_read_url = reverse("servicefile-list")
        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file2.dcm'
        self.post = json.dumps(
            {"template": {"data": [{"name": "path", "value": path},
                                   {"name": "service_name", "value": "MyService"}]}})

    def tearDown(self):
        super(ServiceFileListViewTests, self).tearDown()

    @tag('integration')
    def test_integration_servicefile_create_success(self):
        chris_username = 'chris'
        chris_password = 'chris1234'
        User.objects.create_user(username=chris_username, password=chris_password)

        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file2.dcm'

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

    def test_servicefile_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_servicefile_create_failure_already_exists(self):
        chris_username = 'chris'
        chris_password = 'chris1234'
        User.objects.create_user(username=chris_username, password=chris_password)
        self.client.login(username=chris_username, password=chris_password)
        path = 'SERVICES/MyService/123456-crazy/brain_crazy_study/brain_crazy_mri/file2.dcm'
        service = Service.objects.get(identifier='MyService')
        service_file = ServiceFile(service=service)
        service_file.fname.name = path
        service_file.save()
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_servicefile_create_failure_permission_denied_not_chris_user(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_servicefile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, self.path)

    def test_servicefile_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ServiceFileDetailViewTests(ServiceFileViewTests):
    """
    Test the servicefile-detail view.
    """

    def setUp(self):
        super(ServiceFileDetailViewTests, self).setUp()
        service = Service.objects.get(identifier='MyService')
        service_file = ServiceFile.objects.get(service=service)
        self.read_url = reverse("servicefile-detail",
                                kwargs={"pk": service_file.id})

    def test_servicefile_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, self.path)

    def test_servicefile_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ServiceFileResourceViewTests(ServiceFileViewTests):
    """
    Test the servicefile-resource view.
    """

    def setUp(self):
        super(ServiceFileResourceViewTests, self).setUp()
        service = Service.objects.get(identifier='MyService')
        service_file = ServiceFile.objects.get(service=service)
        self.download_url = reverse("servicefile-resource",
                                    kwargs={"pk": service_file.id}) + 'file1.dcm'

    def tearDown(self):
        super(ServiceFileResourceViewTests, self).tearDown()

    def test_servicefileresource_get(self):
        service = Service.objects.get(identifier='MyService')
        service_file = ServiceFile.objects.get(service=service)
        fileresource_view_inst = mock.Mock()
        fileresource_view_inst.get_object = mock.Mock(return_value=service_file)
        request_mock = mock.Mock()
        with mock.patch('servicefiles.views.Response') as response_mock:
            views.ServiceFileResource.get(fileresource_view_inst, request_mock)
            response_mock.assert_called_with(service_file.fname)

    @tag('integration')
    def test_integration_servicefileresource_download_success(self):
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
