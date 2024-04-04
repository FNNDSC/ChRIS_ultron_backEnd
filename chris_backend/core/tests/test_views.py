
import logging
import json

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from rest_framework import status

import jwt

from userfiles.models import UserFile
from core.models import FileDownloadToken
from core.storage.helpers import mock_storage, connect_storage



class CoreViewTests(TestCase):
    """
    Generic user view tests' setup and tearDown
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
        self.username = 'cube'
        self.password = 'cubepass'
        self.email = 'dev@babymri.org'

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class FileDownloadTokenListViewTests(CoreViewTests):
    """
    Test the filedownloadtoken-list view.
    """

    def setUp(self):
        super(FileDownloadTokenListViewTests, self).setUp()
        user = User.objects.create_user(username=self.username,
                                        email=self.email,
                                        password=self.password)
        dt = timezone.now() + timezone.timedelta(minutes=10)
        token = jwt.encode({'user': user.username, 'exp': dt}, settings.SECRET_KEY,
                           algorithm='HS256')
        (self.token, tf) = FileDownloadToken.objects.get_or_create(token=token,
                                                                   owner=user)
        self.create_read_url = reverse("filedownloadtoken-list")

    def test_integration_file_download_token_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_file_download_token_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_file_download_token_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "token")

    def test_file_download_token_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

class FileDownloadTokenDetailViewTests(CoreViewTests):
    """
    Test the filedownloadtoken-detail view
    """

    def setUp(self):
        super(FileDownloadTokenDetailViewTests, self).setUp()
        user = User.objects.create_user(username=self.username,
                                        email=self.email,
                                        password=self.password)
        dt = timezone.now() + timezone.timedelta(minutes=10)
        token = jwt.encode({'user': user.username, 'exp': dt}, settings.SECRET_KEY,
                           algorithm='HS256')
        (self.token, tf) = FileDownloadToken.objects.get_or_create(token=token,
                                                                   owner=user)
        self.read_url = reverse("filedownloadtoken-detail",
                                kwargs={"pk": self.token.id})

    def test_file_download_token_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'token')
        self.assertContains(response, self.token)

    def test_file_download_token_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_file_download_token_detail_failure_access_denied(self):
        User.objects.create_user(username='boo', email='boo@gmail.com',
                                 password='boopass')
        self.client.login(username='boo', password='boopass')
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
