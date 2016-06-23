
import json

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from rest_framework import status

from plugins.models import Plugin
from plugins import views


class ViewTests(TestCase):
    
    def setUp(self):
        self.chris_username = 'chris'
        self.chris_password = 'chris12'
        self.username = 'foo'
        self.password = 'bar'
        self.content_type='application/vnd.collection+json'
        
        # create basic models
        
        # create the chris user and another user
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)
        User.objects.create_user(username=self.username,
                                 password=self.password)
        
        # create two plugins
        Plugin.objects.get_or_create(name="pacspull", type="fs")
        Plugin.objects.get_or_create(name="mri_convert", type="ds")


class PluginListViewTests(ViewTests):
    """
    Test the plugin-list view
    """

    def setUp(self):
        super(PluginListViewTests, self).setUp()     
        self.create_read_url = reverse("plugin-list")
        self.post = json.dumps({"template": {"data": [{"name": "name", "value": "mri_deface"},
                                          {"name": "type", "value": "ds"}]}})

    def test_plugin_create_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "mri_deface")
        self.assertEqual(response.data["type"], "ds")

    def test_plugin_create_failure_user_is_not_chris(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "pacspull")
        self.assertContains(response, "mri_convert")

    def test_plugin_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PluginDetailViewTests(ViewTests):
    """
    Test the plugin-detail view
    """

    def setUp(self):
        super(PluginDetailViewTests, self).setUp()     
        plugin = Plugin.objects.get(name="pacspull")
        
        self.read_update_delete_url = reverse("plugin-detail", kwargs={"pk": plugin.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "name", "value": "pacspull_updated"}]}})
          
    def test_plugin_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "pacspull")

    def test_plugin_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_update_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "pacspull_updated")

    def test_feed_update_failure_user_is_not_chris(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_delete_success(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(Plugin.objects.count(), 1)

    def test_plugin_delete_failure_user_is_not_chris(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)




