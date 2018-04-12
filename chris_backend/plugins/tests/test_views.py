
import os
import json
import shutil
from unittest import mock

from django.test import TestCase, tag
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings

from rest_framework import status

from plugins.models import Plugin, PluginParameter, PluginInstance, STATUS_TYPES
from plugins.models import ComputeResource
from plugins.services.manager import PluginManager
from plugins import views

import pudb
import time

class ViewTests(TestCase):
    
    def setUp(self):
        self.chris_username = 'chris'
        self.chris_password = 'chris12'
        self.username = 'data/foo'
        self.password = 'bar'
        self.content_type='application/vnd.collection+json'
        self.compute_resource = ComputeResource.objects.get(
                                                        compute_resource_identifier="host")

        # create basic models
        
        # create the chris user and another user
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)
        User.objects.create_user(username=self.username,
                                 password=self.password)
        
        # create two plugins
        Plugin.objects.get_or_create(name="pacspull", type="fs", 
                                    compute_resource=self.compute_resource)
        Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                    compute_resource=self.compute_resource)


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
        plugin = Plugin.objects.get(name="pacspull")
        self.create_read_url = reverse("plugininstance-list", kwargs={"pk": plugin.id})
        self.post = json.dumps(
            {"template": {"data": [{"name": "dir", "value": "./"}]}})

    def tearDown(self):
        pass

    def test_plugin_instance_create_success(self):
        with mock.patch.object(views.PluginManager, 'run_plugin_app',
                               return_value=None) as run_plugin_app_mock:
            # add parameters to the plugin before the POST request
            plugin = Plugin.objects.get(name="pacspull")
            PluginParameter.objects.get_or_create(plugin=plugin, name='dir', type='string',
                                                  optional=False)
            # make API request
            self.client.login(username=self.username, password=self.password)
            response = self.client.post(self.create_read_url, data=self.post,
                                        content_type=self.content_type)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            # check that manager's run_plugin_app method was called with appropriate args
            (plugin_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin)
            parameters_dict = {'dir': './'}
            run_plugin_app_mock.assert_called_with( plugin_inst,
                                    parameters_dict,
                                    service             = 'pfcon',
                                    inputDirOverride    = '/share/incoming',
                                    outputDirOverride   = '/share/outgoing',
                                    IOPhost='host')

    @tag('integration')
    def test_integration_plugin_instance_create_success(self):
        try:
            # create test directory where files are created
            self.test_dir = settings.MEDIA_ROOT + '/test'
            settings.MEDIA_ROOT = self.test_dir
            if not os.path.exists(self.test_dir):
                os.makedirs(self.test_dir)

            # add a plugin to the system though the plugin manager
            pl_manager = PluginManager()
            pl_manager.add_plugin('fnndsc/pl-simplefsapp', "host")
            plugin = Plugin.objects.get(name="simplefsapp")
            self.create_read_url = reverse("plugininstance-list", kwargs={"pk": plugin.id})

            # create a simplefsapp plugin instance
            user = User.objects.get(username=self.username)
            PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                        compute_resource=plugin.compute_resource)

            # make API request
            self.client.login(username=self.username, password=self.password)
            response = self.client.post(self.create_read_url, data=self.post,
                                        content_type=self.content_type)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        finally:
            # remove test directory
            shutil.rmtree(self.test_dir, ignore_errors=True)
            settings.MEDIA_ROOT = os.path.dirname(self.test_dir)

    def test_plugin_instance_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_instance_list_success(self):
        # create a pacspull plugin instance
        plugin = Plugin.objects.get(name="pacspull")
        user = User.objects.get(username=self.username)
        PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                            compute_resource=plugin.compute_resource)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "pacspull")

    def test_plugin_instance_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginInstanceDetailViewTests(ViewTests):
    """
    Test the plugininstance-detail view
    """

    def setUp(self):
        super(PluginInstanceDetailViewTests, self).setUp()
        # create a pacspull plugin instance
        plugin = Plugin.objects.get(name="pacspull")
        user = User.objects.get(username=self.username)
        (self.pl_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)
        self.read_url = reverse("plugininstance-detail", kwargs={"pk": self.pl_inst.id})

    def test_plugin_instance_detail_success(self):
        with mock.patch.object(views.PluginManager, 'check_plugin_app_exec_status',
                               return_value=None) as check_plugin_app_exec_status_mock:
            # make API request
            self.client.login(username=self.username, password=self.password)
            response = self.client.get(self.read_url)
            self.assertContains(response, "pacspull")

            # check that manager's check_plugin_app_exec_status method was called with
            # appropriate args
            check_plugin_app_exec_status_mock.assert_called_with(self.pl_inst)

    @tag('integration')
    def test_integration_plugin_instance_detail_success(self):
        try:
            # create test directory where files are created
            self.test_dir = settings.MEDIA_ROOT + '/test'
            settings.MEDIA_ROOT = self.test_dir
            if not os.path.exists(self.test_dir):
                os.makedirs(self.test_dir)

            # add a plugin to the system through the plugin manager
            pl_manager = PluginManager()
            pl_manager.add_plugin('fnndsc/pl-simplefsapp', "host")

            # create a simplefsapp plugin instance
            plugin = Plugin.objects.get(name='simplefsapp')
            user = User.objects.get(username=self.username)
            (pl_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                        compute_resource=plugin.compute_resource)
            self.read_url = reverse("plugininstance-detail", kwargs={"pk": pl_inst.id})

            # run the plugin instance
            pl_manager.run_plugin_app(  pl_inst,
                                        {'dir': './'},
                                        service             = 'pfcon',
                                        inputDirOverride    = '/share/incoming',
                                        outputDirOverride   = '/share/outgoing')

            # make API request
            self.client.login(username=self.username, password=self.password)
            response = self.client.get(self.read_url)
            self.assertContains(response, "simplefsapp")

            # After submitting run request, wait before checking status
            # time.sleep(5)

            # In the following we keep checking the status until the job ends with
            # 'finishedSuccessfully'. The code runs in a lazy loop poll with a
            # max number of attempts at 2 second intervals.
            maxLoopTries    = 20
            currentLoop     = 1
            b_checkAgain    = True
            while b_checkAgain:
                response            = self.client.get(self.read_url)
                str_responseStatus  = response.data['status']
                if str_responseStatus == 'finishedSuccessfully':
                    b_checkAgain = False
                else:
                    time.sleep(2)
                currentLoop += 1
                if currentLoop == maxLoopTries:
                    b_checkAgain = False

            self.assertContains(response, "finishedSuccessfully")
        finally:
            # remove test directory
            shutil.rmtree(self.test_dir, ignore_errors=True)
            settings.MEDIA_ROOT = os.path.dirname(self.test_dir)

    def test_plugin_instance_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
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
        (inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin,
                                owner=user,compute_resource=plugin.compute_resource)
        # set first instance's status
        inst.status = STATUS_TYPES[0]
        plugin = Plugin.objects.get(name="mri_convert")
        (inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin,
                                    owner=user, compute_resource=plugin.compute_resource)
        # set second instance's status
        inst.status = STATUS_TYPES[2]

        self.list_url = reverse("plugininstance-list-query-search") + '?status=' + \
                        STATUS_TYPES[0]

    def test_plugin_instance_query_search_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        # response should only contain the instances that match the query
        self.assertContains(response, STATUS_TYPES[0])
        self.assertNotContains(response, STATUS_TYPES[1])

    def test_plugin_instance_query_search_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
