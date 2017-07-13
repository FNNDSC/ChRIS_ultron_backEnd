
import os, json, shutil

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings

from rest_framework import status

from plugins.models import Plugin, PluginParameter, PluginInstance, STATUS_TYPES
from plugins.services.manager import PluginManager
from plugins import views
from plugins.services import charm

import pudb
import time

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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginListQuerySearchViewTests(ViewTests):
    """
    Test the plugin-list-query-search view
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginInstanceListViewTests(ViewTests):
    """
    Test the plugininstance-list view
    """

    def setUp(self):
        super(PluginInstanceListViewTests, self).setUp()
        # create test directory where files are created
        self.test_dir = settings.MEDIA_ROOT + '/test'
        settings.MEDIA_ROOT = self.test_dir
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

        # pudb.set_trace()

        # add a plugin to the system though the plugin manager
        pl_manager = PluginManager()
        # pl_manager.startup_apps_exec_server()
        pl_manager.add_plugin('fnndsc/pl-simplefsapp')
        plugin = Plugin.objects.get(name="simplefsapp")
        self.create_read_url = reverse("plugininstance-list", kwargs={"pk": plugin.id})
        self.post = json.dumps(
            {"template": {"data": [{"name": "dir", "value": "./"}]}})

        # create a plugin instance
        user = User.objects.get(username=self.username)
        PluginInstance.objects.get_or_create(plugin=plugin, owner=user)

    def tearDown(self):
        # remove test directory
        # shutil.rmtree(self.test_dir, ignore_errors=True)
        # print('removing dir %s...' % self.test_dir)
        shutil.rmtree(self.test_dir, ignore_errors=True)
        settings.MEDIA_ROOT = os.path.dirname(self.test_dir)

    def test_plugin_instance_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_plugin_instance_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_instance_list_success(self):
        pl_manager = PluginManager()
        pl_manager.startup_apps_exec_server(clearDB = True)

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "simplefsapp")

        pl_manager.shutdown_apps_exec_server()

    def test_plugin_instance_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginInstanceListQuerySearchViewTests(ViewTests):
    """
    Test the plugininstance-list-query-search view
    """

    def setUp(self):
        super(PluginInstanceListQuerySearchViewTests, self).setUp()
        
        user = User.objects.get(username=self.username)
        
        # create two plugin instances
        plugin = Plugin.objects.get(name="pacspull") 
        (inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user)
        # set first instance's status
        inst.status = STATUS_TYPES[0]
        plugin = Plugin.objects.get(name="mri_convert") 
        (inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user)
        # set second instance's status
        inst.status = STATUS_TYPES[2]

        self.list_url = reverse("plugininstance-list-query-search") + '?status='+ STATUS_TYPES[0]

    def test_plugin_instance_query_search_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        # response should only contain the instances that match the query
        self.assertContains(response, STATUS_TYPES[0])
        self.assertNotContains(response, STATUS_TYPES[1])

    def test_plugin_instance_query_search_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        

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

        user            = User.objects.get(username=self.username)
        plugin          = Plugin.objects.get(name="pacspull")
        (pl_inst, tf)   = PluginInstance.objects.get_or_create(plugin=plugin, owner=user)
        # pudb.set_trace()
        pl_manager = PluginManager()
        pl_manager.startup_apps_exec_server(clearDB = True)

        chris2pman   = charm.Charm(
            d_args      = {'dir': './'},
            plugin_inst = pl_inst,
            plugin_repr = {'selfpath': '/bin',
                           'selfexec': 'ls',
                           'execshell': ''}
        )

        chris2pman.app_manage(method = 'pman')
        time.sleep(5)

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "pacspull")
        pl_manager.shutdown_apps_exec_server()

    def test_plugin_instance_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

