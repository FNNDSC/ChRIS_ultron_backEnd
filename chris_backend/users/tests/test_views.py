
import json

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from rest_framework import status


class UserViewTests(TestCase):
    """
    Generic user view tests' setup and tearDown
    """

    def setUp(self):
        self.content_type = 'application/vnd.collection+json'
        self.username = 'cube'
        self.password = 'cubepass'


class UserCreateViewTests(UserViewTests):
    """
    Test the user-create view
    """

    def setUp(self):
        super(UserCreateViewTests, self).setUp()
        self.create_url = reverse("user-create")
        self.post = json.dumps(
            {"template": {"data": [{"name": "username", "value": self.username},
                                   {"name": "password", "value": self.password}]}})

    def test_user_create_success(self):
        response = self.client.post(self.create_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], self.username)

    def test_user_create_failure_already_exists(self):
        User.objects.create_user(username=self.username, password=self.password)
        response = self.client.post(self.create_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_create_failure_bad_password(self):
        post = json.dumps(
            {"template": {"data": [{"name": "username", "value": "new_user"},
                                   {"name": "password", "value": "small"}]}})
        response = self.client.post(self.create_url, data=post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserListViewTests(UserViewTests):
    """
    Test the user-list view
    """

    def setUp(self):
        super(UserListViewTests, self).setUp()
        self.read_url = reverse("user-list")

    def test_user_list_success(self):
        User.objects.create_user(username=self.username, password=self.password)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, self.username)

    def test_user_list_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserDetailViewTests(UserViewTests):
    """
    Test the user-detail view
    """

    def setUp(self):
        super(UserDetailViewTests, self).setUp()
        user = User.objects.create_user(username=self.username,
                                        password=self.password)
        self.read_update_url = reverse("user-detail", kwargs={"pk": user.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "password", "value": "updated_pass"}]}})

    def test_user_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, self.username)

    def test_user_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, self.username)

    def test_user_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_update_failure_access_denied(self):
        User.objects.create_user(username="other_username", password="other_password")
        self.client.login(username="other_username", password="other_password")
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)