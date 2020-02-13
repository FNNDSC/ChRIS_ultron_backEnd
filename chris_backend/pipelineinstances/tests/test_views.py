
import logging
import json
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from rest_framework import status

from plugins.models import Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultStrParameter, DefaultIntParameter
from plugininstances.models import PluginInstance
from pipelines.models import Pipeline, PluginPiping
from pipelineinstances.models import PipelineInstance


class ViewTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.content_type = 'application/vnd.collection+json'

        self.plugin_fs_name = "simplefsapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': True,
                                             'default': "./"}}
        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'dummyInt': {'type': 'integer', 'optional': True,
                                                  'default': 111111}}
        self.username = 'foo'
        self.password = 'foo-pass'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create plugins
        (plugin_fs, tf) = Plugin.objects.get_or_create(name=self.plugin_fs_name,
                                                       type='fs',
                                                       compute_resource=self.compute_resource)
        (plugin_ds, tf) = Plugin.objects.get_or_create(name=self.plugin_ds_name,
                                                       type='ds',
                                                       compute_resource=self.compute_resource)
        # add plugins' parameters
        (plg_param_fs, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])
        default = self.plugin_fs_parameters['dir']['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_fs,
                                                   value=default)  # set plugin parameter default

        # add a parameter with a default
        (plg_param_ds, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyInt',
            type=self.plugin_ds_parameters['dummyInt']['type'],
            optional=self.plugin_ds_parameters['dummyInt']['optional']
        )
        default = self.plugin_ds_parameters['dummyInt']['default']
        DefaultIntParameter.objects.get_or_create(plugin_param=plg_param_ds,
                                                  value=default)  # set plugin parameter default

        # create user
        user = User.objects.create_user(username=self.username, password=self.password)

        # create a pipeline
        self.pipeline_name = 'Pipeline1'
        (pipeline, tf) = Pipeline.objects.get_or_create(name=self.pipeline_name,
                                                        owner=user, category='test')

        # create two plugin pipings
        self.pips = []
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds,
                                                       pipeline=pipeline)
        self.pips.append(pip)
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds, previous=pip,
                                                       pipeline=pipeline)
        self.pips.append(pip)

        # create another user
        self.other_username = 'boo'
        self.other_password = 'far'
        User.objects.create_user(username=self.other_username, password=self.other_password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PipelineInstanceListViewTests(ViewTests):
    """
    Test the pipelineinstance-list view.
    """

    def setUp(self):
        super(PipelineInstanceListViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        self.create_read_url = reverse("pipelineinstance-list", kwargs={"pk": pipeline.id})
        owner = User.objects.get(username=self.username)
        plugin_fs = Plugin.objects.get(name=self.plugin_fs_name)
        (self.pl_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin_fs, owner=owner,
                                            compute_resource=plugin_fs.compute_resource)

    def test_pipeline_instance_create_success(self):

        plugin_ds = Plugin.objects.get(name=self.plugin_ds_name)
        param_name = "%s_%s_%s_%s" % (plugin_ds.id, self.pips[1].id, self.pips[0].id, 'dummyInt')
        post = json.dumps(
            {"template": {"data": [{"name": "title", "value": "PipelineInst1"},
                                   {"name": "previous_plugin_inst_id", "value": self.pl_inst.id},
                                   {"name": param_name, "value": 333333}]}})
        # make API request
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=post, content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_pipeline_instance_list_success(self):
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        PipelineInstance.objects.get_or_create(title="PipelineInst1", pipeline=pipeline,
                                               owner=owner)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "PipelineInst1")

    def test_pipeline_instance_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PipelineInstanceListQuerySearchViewTests(ViewTests):
    """
    Test the pipelineinstance-list-query-search view.
    """

    def setUp(self):
        super(PipelineInstanceListQuerySearchViewTests, self).setUp()

        self.query_url1 = reverse("allpipelineinstance-list-query-search") + "?title=PipelineInst"
        self.query_url2 = reverse("allpipelineinstance-list-query-search") + "?pipeline_name=" + \
                          self.pipeline_name

    def test_pipeline_instance_query_search_list_success(self):
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        PipelineInstance.objects.get_or_create(title="PipelineInst1", pipeline=pipeline,
                                               owner=owner)
        PipelineInstance.objects.get_or_create(title="PipelineMyInst", pipeline=pipeline,
                                               owner=owner)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.query_url1)
        # response should only contain the instances that match the query
        self.assertContains(response, "PipelineInst1")
        self.assertNotContains(response, "PipelineMyInst")
        response = self.client.get(self.query_url2)
        self.assertContains(response, "PipelineInst1")
        self.assertContains(response, "PipelineMyInst")

    def test_pipeline_instance_query_search_list_failure_unauthenticated(self):
        response = self.client.get(self.query_url1)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PipelineInstanceDetailViewTests(ViewTests):
    """
    Test the pipelineinstance-detail view.
    """

    def setUp(self):
        super(PipelineInstanceDetailViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        (pipeline_inst, tf) = PipelineInstance.objects.get_or_create(title="PipelineInst1",
                                                                     pipeline=pipeline,
                                                                     owner=owner)
        self.read_update_delete_url = reverse("pipelineinstance-detail", kwargs={"pk": pipeline_inst.id})

    def test_pipeline_instance_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "PipelineInst1")

    def test_pipeline_instance_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pipeline_instance_update_success(self):
        put = json.dumps({
            "template": {"data": [{"name": "title", "value": "Test pipeline instance"}]}})

        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=put,
                                   content_type=self.content_type)
        self.assertContains(response, "Test pipeline instance")

    def test_pipeline_instance_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data={},
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pipeline_instance_update_failure_access_denied(self):
        put = json.dumps({
            "template": {"data": [{"name": "title", "value": "Test pipeline instance"}]}})

        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pipeline_instance_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(PipelineInstance.objects.count(), 0)

    def test_pipeline_instance_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pipeline_instance_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PipelineInstancePluginInstanceListViewTests(ViewTests):
    """
    Test the pipelineinstance-plugininstance-list view.
    """

    def setUp(self):
        super(PipelineInstancePluginInstanceListViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        (self.pipeline_inst, tf) = PipelineInstance.objects.get_or_create(title="PipelineInst1",
                                                                          pipeline=pipeline,
                                                                          owner=owner)
        self.list_url = reverse("pipelineinstance-plugininstance-list",
                                kwargs={"pk": self.pipeline_inst.id})

    def test_pipeline_instance_plugin_instance_list_success(self):
        plugin_fs = Plugin.objects.get(name=self.plugin_fs_name)
        owner = User.objects.get(username=self.username)
        (previous_plg_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin_fs,
                                                                  owner=owner,
                                            compute_resource=plugin_fs.compute_resource)
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        for pip in pipeline.plugin_pipings.all():
            plugin_ds = pip.plugin
            (pl_inst_ds, tf) = PluginInstance.objects.get_or_create(plugin=plugin_ds,
                                                                    title="PluginInst" + str(pip.id),
                                                                  owner=owner,
                                                        pipeline_inst=self.pipeline_inst,
                                                            previous=previous_plg_inst,
                                            compute_resource=plugin_fs.compute_resource)
            previous_plg_inst = pl_inst_ds
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        for pip in pipeline.plugin_pipings.all():
            self.assertContains(response, "PluginInst" + str(pip.id))

    def test_pipeline_instance_plugin_instance_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
