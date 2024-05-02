
import logging
import json

from django.test import TestCase, tag
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.conf import settings

from rest_framework import status

from userfiles.models import UserFile
from core.storage.helpers import mock_storage, connect_storage



class ViewTests(TestCase):
    """
    Generic user view tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = 'chris1234'
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password, is_staff=True)

        self.content_type = 'application/vnd.collection+json'
        self.username = 'cube'
        self.password = 'cubepass'
        self.email = 'dev@babymri.org'

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class UserCreateViewTests(ViewTests):
    """
    Test the user-create view.
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

            welcome_file_path = f'home/{self.username}/uploads/welcome.txt'
            self.assertTrue(storage_manager.obj_exists(welcome_file_path))

    @tag('integration')
    def test_integration_user_create_success(self):
        response = self.client.post(self.create_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], self.username)
        self.assertEqual(response.data["email"], self.email)

        user = User.objects.get(username=self.username)
        welcome_file_path = f'home/{self.username}/uploads/welcome.txt'
        welcome_file = UserFile.objects.get(owner=user)
        self.assertEqual(welcome_file.fname.name, welcome_file_path)

        # delete welcome file
        storage_manager = connect_storage(settings)

        storage_manager.delete_obj(welcome_file_path)

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


class UserGroupListViewTests(ViewTests):
    """
    Test the user-group-list view.
    """

    def setUp(self):
        super(UserGroupListViewTests, self).setUp()
        user = User.objects.create_user(username=self.username,
                                        email=self.email,
                                        password=self.password)
        group, _ = Group.objects.get_or_create(name='test_group')
        user.groups.set([group])

        self.read_url = reverse("user-group-list", kwargs={"pk": user.id})

    def test_user_group_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'test_group')

    def test_user_group_list_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserDetailViewTests(ViewTests):
    """
    Test the user-detail view.
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


class GroupListViewTests(ViewTests):
    """
    Test the group-list view.
    """

    def setUp(self):
        super(GroupListViewTests, self).setUp()

        self.create_read_url = reverse("group-list")
        self.post = json.dumps(
            {"template": {"data": [{"name": "name", "value": "test_group"}]}})

        user = User.objects.create_user(username=self.username,
                                        email=self.email,
                                        password=self.password)

        # create two groups
        Group.objects.get_or_create(name='G1')
        Group.objects.get_or_create(name='G2')
    def test_group_create_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "test_group")

    def test_group_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_group_create_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_group_list_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "G1")
        self.assertContains(response, "G2")

    def test_group_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_group_list_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GroupDetailViewTests(ViewTests):
    """
    Test the group-detail view.
    """

    def setUp(self):
        super(GroupDetailViewTests, self).setUp()

        User.objects.create_user(username=self.username, email=self.email,
                                 password=self.password)

        # create a group
        group, _ = Group.objects.get_or_create(name="G3")

        self.read_delete_url = reverse("group-detail", kwargs={"pk": group.id})

    def test_group_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_delete_url)
        self.assertContains(response, 'G3')

    def test_group_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_group_delete_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Group.objects.count(), 0)

    def test_group_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_group_delete_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GroupUserListViewTests(ViewTests):
    """
    Test the group-user-list view.
    """

    def setUp(self):
        super(GroupUserListViewTests, self).setUp()

        self.post = json.dumps(
            {"template": {"data": [{"name": "username", "value": "fooboo"}]}})

        User.objects.create_user(username='fooboo', email='foo@gmail.com',
                                 password='foopass')

        user = User.objects.create_user(username=self.username, email=self.email,
                                        password=self.password)
        group, _ = Group.objects.get_or_create(name='mygroup')
        user.groups.set([group])

        self.create_read_url = reverse("group-user-list", kwargs={"pk": group.id})

    def test_group_user_create_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user_username"], "fooboo")

    def test_group_user_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_group_user_create_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_group_user_list_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.create_read_url)

        self.assertContains(response, self.username)
        self.assertContains(response, "mygroup")

    def test_group_user_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_group_user_list_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GroupUserDetailViewTests(ViewTests):
    """
    Test the user_groups-detail view.
    """

    def setUp(self):
        super(GroupUserDetailViewTests, self).setUp()

        user = User.objects.create_user(username=self.username, email=self.email,
                                        password=self.password)
        # create a group
        group, _ = Group.objects.get_or_create(name="G4")

        user.groups.set([group])
        group_user = User.groups.through.objects.get(user=user, group=group)

        self.read_delete_url = reverse("user_groups-detail", kwargs={"pk": group_user.id})

    def test_group_user_detail_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.read_delete_url)
        self.assertContains(response, 'G4')
        self.assertContains(response, self.username)

    def test_group_user_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_group_user_detail_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_group_user_delete_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(User.groups.through.objects.count(), 0)

    def test_group_user_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_group_user_delete_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
