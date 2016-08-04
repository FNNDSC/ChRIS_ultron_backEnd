
import os, json

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings

from rest_framework import status

from plugins.models import Plugin, PluginParameter, PluginInstance
from plugins.services.manager import PluginManager
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
        self.list_url = reverse("plugin-list")

    def test_plugin_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "pacspull")
        self.assertContains(response, "mri_convert")

    def test_plugin_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PluginDetailViewTests(ViewTests):
    """
    Test the plugin-detail view
    """

    def setUp(self):
        super(PluginDetailViewTests, self).setUp()     
        plugin = Plugin.objects.get(name="pacspull")
        
        self.read_url = reverse("plugin-detail", kwargs={"pk": plugin.id})
          
    def test_plugin_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "pacspull")

    def test_plugin_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PluginParameterListViewTests(ViewTests):
    """
    Test the pluginparameter-list view
    """

    def setUp(self):
        super(PluginParameterListViewTests, self).setUp()
        plugin = Plugin.objects.get(name="pacspull")
        #self.corresponding_plugin_url = reverse("plugin-detail", kwargs={"pk": plugin.id})
        self.list_url = reverse("pluginparameter-list", kwargs={"pk": plugin.id})

        # create two plugin parameters
        PluginParameter.objects.get_or_create(plugin=plugin,
                                              name='img_type', type='string')
        PluginParameter.objects.get_or_create(plugin=plugin,
                                              name='prefix', type='string')

    def test_plugin_parameter_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "img_type")
        self.assertContains(response, "prefix")

    def test_plugin_parameter_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PluginParameterDetailViewTests(ViewTests):
    """
    Test the pluginparameter-detail view
    """

    def setUp(self):
        super(PluginParameterDetailViewTests, self).setUp()     
        plugin = Plugin.objects.get(name="pacspull")
        # create a plugin parameter
        (param, tf) = PluginParameter.objects.get_or_create(plugin=plugin,
                                                                name='mrn', type='string')  
        self.read_url = reverse("pluginparameter-detail",
                                              kwargs={"pk": param.id})
          
    def test_plugin_parameter_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "mrn")

    def test_plugin_parameter_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PluginInstanceListViewTests(ViewTests):
    """
    Test the plugininstance-list view
    """

    def setUp(self):
        super(PluginInstanceListViewTests, self).setUp()
        # add a plugin to the system though the plugin manager
        pl_manager = PluginManager()
        pl_manager.add_plugin('simpleapp')
        plugin = Plugin.objects.get(name="simpleapp")
        self.create_read_url = reverse("plugininstance-list", kwargs={"pk": plugin.id})
        self.post = json.dumps(
            {"template": {"data": [{"name": "dir", "value": "./"}]}})

        # create a plugin instance
        user = User.objects.get(username=self.username)
        PluginInstance.objects.get_or_create(plugin=plugin, owner=user)

    def test_plugin_instance_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_plugin_instance_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_instance_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "simpleapp")

    def test_plugin_instance_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        

class PluginInstanceDetailViewTests(ViewTests):
    """
    Test the plugininstance-detail view
    """

    def setUp(self):
        super(PluginInstanceDetailViewTests, self).setUp()
        plugin = Plugin.objects.get(name="pacspull")

        # create a plugin instance
        user = User.objects.get(username=self.username)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user)

        self.read_url = reverse("plugininstance-detail", kwargs={"pk": pl_inst.id})       
         
    def test_plugin_instance_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "pacspull")

    def test_plugin_instance_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

