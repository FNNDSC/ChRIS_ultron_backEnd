
import logging

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from rest_framework import status

from plugins.models import Plugin, PluginParameter
from plugins.models import ComputeResource


class ViewTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.username = 'data/foo'
        self.password = 'bar'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create API user
        User.objects.create_user(username=self.username,
                                 password=self.password)
        
        # create two plugins
        Plugin.objects.get_or_create(name="pacspull", type="fs", 
                                    compute_resource=self.compute_resource)
        Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                    compute_resource=self.compute_resource)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PluginListViewTests(ViewTests):
    """
    Test the plugin-list view.
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginListQuerySearchViewTests(ViewTests):
    """
    Test the plugin-list-query-search view.
    """

    def setUp(self):
        super(PluginListQuerySearchViewTests, self).setUp()     
        self.list_url = reverse("plugin-list-query-search") + '?name=pacspull'

    def test_plugin_list_query_search_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "pacspull")
        self.assertNotContains(response, "mri_convert")

    def test_plugin_list_query_search_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginDetailViewTests(ViewTests):
    """
    Test the plugin-detail view.
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginParameterListViewTests(ViewTests):
    """
    Test the pluginparameter-list view.
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginParameterDetailViewTests(ViewTests):
    """
    Test the pluginparameter-detail view.
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
