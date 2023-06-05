
import logging
import json

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

from rest_framework import status

from uploadedfiles.models import UploadedFile
from core.storage.helpers import mock_storage, connect_storage



class UserViewTests(TestCase):
    """
    Generic user view tests' setup and tearDown
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.content_type = 'application/vnd.collection+json'
        self.username = 'cube'
        self.password = 'cubepass'
        self.email = 'dev@babymri.org'

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class UserCreateViewTests(UserViewTests):
    """
    Test the user-create view
    """

    def setUp(self):
        super(UserCreateViewTests, self).setUp()
        self.create_url = reverse("user-create")
        self.post = json.dumps(
            {"template": {"data": [{"name": "username", "value": self.username},
                                   {"name": "password", "value": self.password},
                                   {"name": "email", "value": self.email}]}})

    def test_user_create_success(self):
        with mock_storage('users.serializers.settings') as storage_manager:
            response = self.client.post(self.create_url, data=self.post,
                                        content_type=self.content_type)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data["username"], self.username)
            self.assertEqual(response.data["email"], self.email)

            welcome_file_path = '%s/uploads/welcome.txt' % self.username
            self.assertTrue(storage_manager.obj_exists(welcome_file_path))

    @tag('integration')
    def test_integration_user_create_success(self):
        response = self.client.post(self.create_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], self.username)
        self.assertEqual(response.data["email"], self.email)

        user = User.objects.get(username=self.username)
        welcome_file_path = '%s/uploads/welcome.txt' % self.username
        welcome_file = UploadedFile.objects.get(owner=user)
        self.assertEqual(welcome_file.fname.name, welcome_file_path)

        # delete welcome file
        swift_manager = connect_storage(settings)

        swift_manager.delete_obj(welcome_file_path)

    def test_user_create_failure_already_exists(self):
        User.objects.create_user(username=self.username,
                                 email=self.email,
                                 password=self.password)
        response = self.client.post(self.create_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_create_failure_bad_password(self):
        post = json.dumps(
            {"template": {"data": [{"name": "username", "value": "new_user"},
                                   {"name": "email", "value": self.email},
                                   {"name": "password", "value": "small"}]}})
        response = self.client.post(self.create_url, data=post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserDetailViewTests(UserViewTests):
    """
    Test the user-detail view
    """

    def setUp(self):
        super(UserDetailViewTests, self).setUp()
        user = User.objects.create_user(username=self.username,
                                        email=self.email,
                                        password=self.password)
        self.read_update_url = reverse("user-detail", kwargs={"pk": user.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "password", "value": "updated_pass"},
                                  {"name": "email", "value": "dev1@babymri.org"}]}})

    def test_user_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, self.username)
        self.assertContains(response, self.email)

    def test_user_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, self.username)
        self.assertContains(response, "dev1@babymri.org")

    def test_user_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_update_failure_access_denied(self):
        User.objects.create_user(username="other_username", email="dev2@babymri.org",
                                 password="other_password")
        self.client.login(username="other_username", password="other_password")
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)