
import logging
import json
import time
import io
from unittest import mock

from django.test import TestCase, tag
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings

from rest_framework import status

import swiftclient

from plugins.models import Plugin, PluginParameter, ComputeResource
from plugininstances.models import PluginInstance, PluginInstanceFile
from plugininstances.models import PathParameter, FloatParameter, STATUS_TYPES
from plugininstances.services.manager import PluginAppManager
from plugininstances import views


class ViewTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.chris_username = 'chris'
        self.chris_password = 'chris12'
        self.username = 'data/foo'
        self.password = 'bar'
        self.other_username = 'boo'
        self.other_password = 'far'

        self.content_type='application/vnd.collection+json'
        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create the chris superuser and two additional users
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
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


class PluginInstanceListViewTests(ViewTests):
    """
    Test the plugininstance-list view.
    """

    def setUp(self):
        super(PluginInstanceListViewTests, self).setUp()
        plugin = Plugin.objects.get(name="pacspull")
        self.create_read_url = reverse("plugininstance-list", kwargs={"pk": plugin.id})
        self.post = json.dumps(
            {"template": {"data": [{"name": "dir", "value": "./"}]}})

    def test_plugin_instance_create_success(self):
        with mock.patch.object(views.PluginAppManager, 'run_plugin_app',
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
                                    outputDirOverride   = '/share/outgoing')

    @tag('integration')
    def test_integration_plugin_instance_create_success(self):
        # add an FS plugin to the system
        plugin_repr =      {"name": "simplefsapp",
                            "dock_image": "fnndsc/pl-simplefsapp",
                            "authors": "FNNDSC (dev@babyMRI.org)", "type": "fs",
                            "description": "A simple chris fs app demo",
                            "version": "0.1",
                            "title": "Simple chris fs app",
                            "license": "Opensource (MIT)",

                            "parameters": [{"optional": True, "action": "store",
                                            "help": "look up directory",
                                            "type": "path",
                                            "name": "dir", "flag": "--dir",
                                            "default": "./"}],

                            "selfpath": "/usr/src/simplefsapp",
                            "selfexec": "simplefsapp.py", "execshell": "python3"}
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")
        parameters = plugin_repr['parameters']
        data = plugin_repr
        del data['parameters']
        data['compute_resource'] = compute_resource
        (plugin, tf) = Plugin.objects.get_or_create(**data)

        # add plugin's parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'])

        # create a plugin's instance
        user = User.objects.get(username=self.username)
        PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                    compute_resource=plugin.compute_resource)

        # make POST API request
        self.create_read_url = reverse("plugininstance-list", kwargs={"pk": plugin.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

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
    Test the plugininstance-detail view.
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
        with mock.patch.object(views.PluginAppManager, 'check_plugin_app_exec_status',
                               return_value=None) as check_plugin_app_exec_status_mock:
            # make API request
            self.client.login(username=self.username, password=self.password)
            response = self.client.get(self.read_url)
            self.assertContains(response, "pacspull")

            # check that manager's check_plugin_app_exec_status method was called with
            # appropriate args
            check_plugin_app_exec_status_mock.assert_called_with(self.pl_inst)

    @tag('integration', 'error-pman')
    def test_integration_plugin_instance_detail_success(self):
        # add an FS plugin to the system
        plugin_repr = {"name": "simplefsapp",
                       "dock_image": "fnndsc/pl-simplefsapp",
                       "authors": "FNNDSC (dev@babyMRI.org)", "type": "fs",
                       "description": "A simple chris fs app demo",
                       "version": "0.1",
                       "title": "Simple chris fs app",
                       "license": "Opensource (MIT)",

                       "parameters": [{"optional": True, "action": "store",
                                       "help": "look up directory",
                                       "type": "path",
                                       "name": "dir", "flag": "--dir",
                                       "default": "./"}],

                       "selfpath": "/usr/src/simplefsapp",
                       "selfexec": "simplefsapp.py", "execshell": "python3"}
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")
        parameters = plugin_repr['parameters']
        data = plugin_repr
        del data['parameters']
        data['compute_resource'] = compute_resource
        (plugin, tf) = Plugin.objects.get_or_create(**data)

        # add plugin's parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'])

        # create a plugin's instance
        user = User.objects.get(username=self.username)
        (pl_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                    compute_resource=plugin.compute_resource)
        self.read_url = reverse("plugininstance-detail", kwargs={"pk": pl_inst.id})

        # run the plugin instance
        PluginAppManager.run_plugin_app(  pl_inst,
                                    {'dir': './'},
                                    service             = 'pfcon',
                                    inputDirOverride    = '/share/incoming',
                                    outputDirOverride   = '/share/outgoing')

        # make API GET request
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "simplefsapp")

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

    def test_plugin_instance_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginInstanceListQuerySearchViewTests(ViewTests):
    """
    Test the plugininstance-list-query-search view.
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
        (inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                                          previous=inst,
                                                compute_resource=plugin.compute_resource)
        # set second instance's status
        inst.status = STATUS_TYPES[2]

        self.list_url = reverse("allplugininstance-list-query-search") + '?status=' + \
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


class PluginInstanceDescendantListViewTests(ViewTests):
    """
    Test the plugininstance-descendant-list view.
    """

    def setUp(self):
        super(PluginInstanceDescendantListViewTests, self).setUp()

        user = User.objects.get(username=self.username)

        # create an 'fs' plugin instance
        plugin = Plugin.objects.get(name="pacspull")
        (fs_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)

        # create a tree of 'ds' plugin instances
        plugin = Plugin.objects.get(name="mri_convert")
        PluginInstance.objects.get_or_create(plugin=plugin, owner=user, previous=fs_inst,
                                             compute_resource=plugin.compute_resource)

        (plugin, tf) = Plugin.objects.get_or_create(name="mri_info", type="ds",
                                    compute_resource=self.compute_resource)
        (ds_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                previous=fs_inst, compute_resource=plugin.compute_resource)

        (plugin, tf) = Plugin.objects.get_or_create(name="mri_surf", type="ds",
                                    compute_resource=self.compute_resource)
        PluginInstance.objects.get_or_create(plugin=plugin, owner=user, previous=ds_inst,
                                             compute_resource=plugin.compute_resource)

        self.list_url = reverse("plugininstance-descendant-list", kwargs={"pk": fs_inst.id})

    def test_plugin_instance_descendant_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        # response should contain all the instances in the tree
        self.assertContains(response, "pacspull")
        self.assertContains(response, "mri_convert")
        self.assertContains(response, "mri_info")
        self.assertContains(response, "mri_surf")

    def test_plugin_instance_descendant_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginInstanceParameterListViewTests(ViewTests):
    """
    Test the plugininstance-parameter-list view.
    """

    def setUp(self):
        super(PluginInstanceParameterListViewTests, self).setUp()

        user = User.objects.get(username=self.username)

        # create a plugin
        plugin = Plugin.objects.get(name="pacspull")
        parameters = [{"type": "path", "name": "param1", "flag": "--param1"},
                      {"type": "float", "name": "param2", "flag": "--param2"}]

        # add plugin's parameters
        (param1, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'])
        (param2, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=parameters[1]['name'],
            type=parameters[1]['type'],
            flag=parameters[1]['flag'])

        # create a plugin instance
        (inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)

        # create two plugin parameter instances associated to the plugin instance
        PathParameter.objects.get_or_create(plugin_inst=inst, plugin_param=param1,
                                            value="./")
        FloatParameter.objects.get_or_create(plugin_inst=inst, plugin_param=param2,
                                             value=3.14)

        self.list_url = reverse("plugininstance-parameter-list", kwargs={"pk": inst.id})

    def test_plugin_instance_parameter_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "param1")
        self.assertContains(response, "./")
        self.assertContains(response, "param2")
        self.assertContains(response, 3.14)

    def test_plugin_instance_parameter_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginInstanceFileViewTests(ViewTests):
    """
    Generic plugin instance file view tests' setup and tearDown.
    """

    def setUp(self):
        super(PluginInstanceFileViewTests, self).setUp()
        # create a plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name="pacspull")
        (self.plg_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin,
                                                                   owner=user,
                                                compute_resource=plugin.compute_resource)
        # create test directory where files are created
        # self.test_dir = settings.MEDIA_ROOT + '/test'
        # settings.MEDIA_ROOT = self.test_dir
        # if not os.path.exists(self.test_dir):
        #     os.makedirs(self.test_dir)

    def tearDown(self):
        super(PluginInstanceFileViewTests, self).tearDown()
        # remove test directory
        # shutil.rmtree(self.test_dir)
        # settings.MEDIA_ROOT = os.path.dirname(self.test_dir)


class PluginInstanceFileListViewTests(PluginInstanceFileViewTests):
    """
    Test the plugininstancefile-list view.
    """

    def setUp(self):
        super(PluginInstanceFileListViewTests, self).setUp()

        # create a plugin instance file associated to the plugin instance
        plg_inst = self.plg_inst
        (plg_inst_file, tf) = PluginInstanceFile.objects.get_or_create(plugin_inst=plg_inst)
        plg_inst_file.fname.name = 'test_file.txt'
        plg_inst_file.save()

        self.list_url = reverse("plugininstancefile-list", kwargs={"pk": plg_inst.id})

    def test_plugin_instance_file_create_failure_post_not_allowed(self):
        self.client.login(username=self.username, password=self.password)
        # try to create a new plugin file with a POST request to the list
        # POST request using multipart/form-data to be able to upload file
        with io.StringIO("test file") as f:
            post = {"fname": f}
            response = self.client.post(self.list_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_plugin_instance_file_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "test_file.txt")

    def test_plugin_instance_file_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_instance_file_list_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PluginInstanceFileDetailViewTests(PluginInstanceFileViewTests):
    """
    Test the plugininstancefile-detail view.
    """

    def setUp(self):
        super(PluginInstanceFileDetailViewTests, self).setUp()
        #self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})
        plg_inst = self.plg_inst
        self.corresponding_plugin_instance_url = reverse("plugininstance-detail",
                                                         kwargs={"pk": plg_inst.id})

        # create a file in the DB "already uploaded" to the server
        (plg_inst_file, tf) = PluginInstanceFile.objects.get_or_create(plugin_inst=plg_inst)
        plg_inst_file.fname.name = 'file1.txt'
        plg_inst_file.save()

        self.read_url = reverse("plugininstancefile-detail",
                                kwargs={"pk": plg_inst_file.id})

    def test_plugin_instance_file_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "file1.txt")
        self.assertTrue(response.data["plugin_inst"].endswith(
            self.corresponding_plugin_instance_url))

    def test_plugin_instance_file_detail_success_user_chris(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "file1.txt")
        self.assertTrue(response.data["plugin_inst"].endswith(
            self.corresponding_plugin_instance_url))

    def test_plugin_instance_file_detail_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_instance_file_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FileResourceViewTests(PluginInstanceFileViewTests):
    """
    Test the plugininstancefile-resource view.
    """

    def setUp(self):
        super(FileResourceViewTests, self).setUp()
        plg_inst = self.plg_inst
        # create a file in the DB "already uploaded" to the server
        (plg_inst_file, tf) = PluginInstanceFile.objects.get_or_create(
            plugin_inst=plg_inst)
        plg_inst_file.fname.name = '/tests/file1.txt'
        plg_inst_file.save()
        self.download_url = reverse("plugininstancefile-resource",
                                    kwargs={"pk": plg_inst_file.id}) + 'file1.txt'

    def test_fileresource_get(self):
        plg_inst_file = PluginInstanceFile.objects.get(fname="/tests/file1.txt")
        fileresource_view_inst = mock.Mock()
        fileresource_view_inst.get_object = mock.Mock(return_value=plg_inst_file)
        request_mock = mock.Mock()
        with mock.patch('plugininstances.views.Response') as response_mock:
            views.FileResource.get(fileresource_view_inst, request_mock)
            response_mock.assert_called_with(plg_inst_file.fname)

    @tag('integration')
    def test_integration_fileresource_download_success(self):
        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # upload file to Swift storage
        with io.StringIO("test file") as file1:
            conn.put_object(settings.SWIFT_CONTAINER_NAME, '/tests/file1.txt',
                            contents=file1.read(),
                            content_type='text/plain')

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.content, 'utf-8'), "test file")

        # delete file from Swift storage
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, '/tests/file1.txt')

    def test_fileresource_download_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fileresource_download_failure_unauthenticated(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
