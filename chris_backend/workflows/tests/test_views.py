
import logging
import json
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import status

from plugins.models import PluginMeta, Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultStrParameter, DefaultIntParameter
from plugininstances.models import PluginInstance
from pipelines.models import Pipeline, PluginPiping
from workflows.models import Workflow
from workflows import views


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class ViewTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

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
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create plugins
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_fs_name, type='fs')
        (plugin_fs, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_fs.compute_resources.set([self.compute_resource])
        plugin_fs.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ds_name, type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

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
        logging.disable(logging.NOTSET)


class WorkflowListViewTests(ViewTests):
    """
    Test the workflow-list view.
    """

    def setUp(self):
        super(WorkflowListViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        self.create_read_url = reverse("workflow-list", kwargs={"pk": pipeline.id})
        owner = User.objects.get(username=self.username)
        plugin_fs = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (self.pl_inst, tf) = PluginInstance.objects.get_or_create(
            status='finishedSuccessfully',
            plugin=plugin_fs, owner=owner,
            compute_resource=plugin_fs.compute_resources.all()[0]
        )

    def test_workflow_create_success(self):
        post = json.dumps(
            {"template": {"data": [{"name": "previous_plugin_inst_id", "value": self.pl_inst.id},
                                   {"name": "nodes_info",
                                    "value": json.dumps([{"piping_id": self.pips[0].id,
                                           "compute_resource_name": "host", "title": "Inst1",
                                           "plugin_parameter_defaults": [
                                               {"name": "dummyInt", "default": 3}]},
                                          {"piping_id": self.pips[1].id,
                                           "compute_resource_name": "host"}])}]}})

        plg_instances_count = PluginInstance.objects.count()
        with mock.patch.object(views.run_plugin_instance, 'delay',
                               return_value=None) as delay_mock:
            self.client.login(username=self.username, password=self.password)
            response = self.client.post(self.create_read_url, data=post,
                                        content_type=self.content_type)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(PluginInstance.objects.count(), plg_instances_count + 2)

    def test_workflow_list_success(self):
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        Workflow.objects.get_or_create(created_plugin_inst_ids="1,2",
                                               pipeline=pipeline,
                                               owner=owner)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "1,2")

    def test_workflow_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class WorkflowListQuerySearchViewTests(ViewTests):
    """
    Test the workflow-list-query-search view.
    """

    def setUp(self):
        super(WorkflowListQuerySearchViewTests, self).setUp()

        self.query_url = reverse("allworkflow-list-query-search") + f"?owner_username={self.username}"

    def test_workflow_query_search_list_success(self):
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        Workflow.objects.get_or_create(created_plugin_inst_ids="1,2",
                                               pipeline=pipeline,
                                               owner=owner)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.query_url)
        self.assertContains(response, self.username)

    def test_workflow_query_search_list_failure_unauthenticated(self):
        response = self.client.get(self.query_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class WorkflowDetailViewTests(ViewTests):
    """
    Test the workflow-detail view.
    """

    def setUp(self):
        super(WorkflowDetailViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        (workflow, tf) = Workflow.objects.get_or_create(created_plugin_inst_ids="1,2",
                                                        pipeline=pipeline, owner=owner)
        self.read_delete_url = reverse("workflow-detail", kwargs={"pk": workflow.id})

    def test_workflow_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_delete_url)
        self.assertContains(response, "1,2")

    def test_workflow_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_workflow_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Workflow.objects.count(), 0)

    def test_workflow_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_workflow_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
