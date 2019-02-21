
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


class PipelineViewTests(ViewTests):
    """
    Generic tests for pipeline views.
    """

    def setUp(self):
        super(PipelineViewTests, self).setUp()
        self.content_type = 'application/vnd.collection+json'
        self.other_username = 'boo'
        self.other_password = 'far'
        self.pipeline_name = 'Pipeline1'
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        user = User.objects.get(username=self.username)
        Pipeline.objects.get_or_create(name=self.pipeline_name, owner=user,
                                       category='test')


class PipelineListViewTests(PipelineViewTests):
    """
    Test the pipeline-list view.
    """

    def setUp(self):
        super(PipelineListViewTests, self).setUp()
        self.create_read_url = reverse("pipeline-list")

    def test_pipeline_create_success(self):
        (plugin_ds1, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        (plugin_ds2, tf) = Plugin.objects.get_or_create(name="mri_analyze", type="ds",
                                                compute_resource=self.compute_resource)

        plugin_id_tree = '[{"plugin_id": ' + str(plugin_ds1.id) + \
                         ', "previous_index": null}, {"plugin_id": ' + \
                         str(plugin_ds2.id) + ', "previous_index": 0}]'
        post = json.dumps(
            {"template": {"data": [{"name": "name", "value": "Pipeline2"},
                                   {"name": "plugin_id_tree", "value": plugin_id_tree}]}})

        # make API request
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_pipeline_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "Pipeline1")

    def test_pipeline_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PipelineListQuerySearchViewTests(PipelineViewTests):
    """
    Test the pipeline-list-query-search view.
    """

    def setUp(self):
        super(PipelineListQuerySearchViewTests, self).setUp()
        self.list_url = reverse("pipeline-list-query-search") + '?name=Pipeline1'

    def test_plugin_list_query_search_success(self):
        owner = User.objects.get(username=self.username)
        Pipeline.objects.get_or_create(name='Pipeline2', owner=owner,
                                       category='test')
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "Pipeline1")
        self.assertNotContains(response, "Pipeline2")
        list_url = reverse("pipeline-list-query-search") + '?category=test'
        response = self.client.get(list_url)
        self.assertContains(response, "Pipeline1")
        self.assertContains(response, "Pipeline2")

    def test_plugin_list_query_search_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PipelineDetailViewTests(PipelineViewTests):
    """
    Test the pipeline-detail view.
    """

    def setUp(self):
        super(PipelineDetailViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name="Pipeline1")
        self.read_update_delete_url = reverse("pipeline-detail", kwargs={"pk": pipeline.id})
        self.put = json.dumps(
            {"template": {"data": [{"name": "name", "value": "Pipeline2"}]}})

    def test_pipeline_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "Pipeline1")

    def test_pipeline_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pipeline_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Pipeline2")

    def test_pipeline_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pipeline_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pipeline_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Pipeline.objects.count(), 0)

    def test_pipeline_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pipeline_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PipelinePluginListViewTests(PipelineViewTests):
    """
    Test the pipeline-plugin-list view.
    """

    def setUp(self):
        super(PipelinePluginListViewTests, self).setUp()
        self.pipeline = Pipeline.objects.get(name="Pipeline1")
        self.list_url = reverse("pipeline-plugin-list", kwargs={"pk": self.pipeline.id})

    def test_pipeline_plugin_list_success(self):
        # create plugins
        (plugin_ds1, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        Plugin.objects.get_or_create(name="mri_analyze", type="ds",
                                     compute_resource=self.compute_resource)
        # pipe one plugin into pipeline
        PluginPiping.objects.get_or_create(pipeline=self.pipeline, plugin=plugin_ds1,
                                           previous=None)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "mri_convert")
        self.assertNotContains(response, "mri_analyze")  # plugin list is pipe-specific

    def test_pipeline_plugin_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PipelinePluginPipingListViewTests(PipelineViewTests):
    """
    Test the pipeline-pluginpiping-list view.
    """

    def setUp(self):
        super(PipelinePluginPipingListViewTests, self).setUp()
        self.pipeline = Pipeline.objects.get(name="Pipeline1")
        self.list_url = reverse("pipeline-pluginpiping-list",
                                kwargs={"pk": self.pipeline.id})

    def test_pipeline_plugin_piping_list_success(self):
        # create plugins
        (plugin_ds, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        # pipe one plugin into pipeline
        PluginPiping.objects.get_or_create(pipeline=self.pipeline, plugin=plugin_ds,
                                           previous=None)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "plugin_id")

    def test_pipeline_plugin_piping_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginPipingDetailViewTests(PipelineViewTests):
    """
    Test the pluginpiping-detail view.
    """

    def setUp(self):
        super(PluginPipingDetailViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name="Pipeline1")
        # create plugins
        (plugin_ds, tf) = Plugin.objects.get_or_create(name="mri_convert", type="ds",
                                                compute_resource=self.compute_resource)
        # pipe one plugin into pipeline
        (piping, tf) = PluginPiping.objects.get_or_create(pipeline=pipeline,
                                                          plugin=plugin_ds, previous=None)

        self.read_url = reverse("pluginpiping-detail", kwargs={"pk": piping.id})

    def test_plugin_piping_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "plugin_id")
        self.assertContains(response, "pipeline_id")

    def test_plugin_piping_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
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
        with mock.patch('plugins.views.Response') as response_mock:
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
        # create container in case it doesn't already exist
        conn.put_container(settings.SWIFT_CONTAINER_NAME)

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
        with mock.patch('plugins.views.Response') as response_mock:
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
        # create container in case it doesn't already exist
        conn.put_container(settings.SWIFT_CONTAINER_NAME)

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
