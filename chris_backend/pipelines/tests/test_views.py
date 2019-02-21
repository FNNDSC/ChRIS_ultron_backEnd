
import logging
import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from rest_framework import status

from plugins.models import Plugin
from plugins.models import ComputeResource
from pipelines.models import Pipeline, PluginPiping


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
