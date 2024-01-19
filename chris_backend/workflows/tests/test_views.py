
import json
import logging
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from pipelines.models import Pipeline, PluginPiping, DEFAULT_PIPING_PARAMETER_MODELS
from plugininstances.models import PluginInstance
from plugininstances.utils import run_plugin_instance
from plugins.models import ComputeResource
from plugins.models import PluginMeta, Plugin
from plugins.models import PluginParameter, DefaultStrParameter, DefaultIntParameter
from workflows.models import Workflow

COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class ViewTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = 'chris1234'
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)

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

        # add plugins' parameters
        (plg_param_fs, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])
        default = self.plugin_fs_parameters['dir']['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_fs,
                                                   value=default)  # set plugin parameter default

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ds_name, type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

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

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='ts_copy', type='ts')
        (plugin_ts, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ts.compute_resources.set([self.compute_resource])
        plugin_ts.save()

        # add a parameter with a default
        (plg_param_ts, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ts,
            name='plugininstances',
            type='string',
            optional=True
        )
        default = ""
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_ts,
                                                  value=default)  # set plugin parameter default

        # create user
        user = User.objects.create_user(username=self.username, password=self.password)

        # create a pipeline
        self.pipeline_name = 'Pipeline1'
        (pipeline, tf) = Pipeline.objects.get_or_create(name=self.pipeline_name,
                                                        owner=user, category='test')

        # create three plugin pipings
        self.pips = []
        (pip1, tf) = PluginPiping.objects.get_or_create(title='pip_ds1', plugin=plugin_ds,
                                                       pipeline=pipeline)
        self.pips.append(pip1)
        (pip2, tf) = PluginPiping.objects.get_or_create(title='pip_ds2', plugin=plugin_ds,
                                                       previous=pip1, pipeline=pipeline)
        self.pips.append(pip2)
        (pip3, tf) = PluginPiping.objects.get_or_create(title='pip_ts', plugin=plugin_ts,
                                                        previous=pip1, pipeline=pipeline)
        self.pips.append(pip3)
        default_model_class = DEFAULT_PIPING_PARAMETER_MODELS['string']
        (default_piping_param, tf) = default_model_class.objects.get_or_create(
                plugin_piping=pip3, plugin_param=plg_param_ts)
        default_piping_param.value = f"{pip1.id},{pip2.id}"
        default_piping_param.save()

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
                                           "compute_resource_name": "host", "title": "Inst_ds1",
                                           "plugin_parameter_defaults": [
                                               {"name": "dummyInt", "default": 3}]},
                                          {"piping_id": self.pips[1].id, "title": "Inst_ds2",
                                           "compute_resource_name": "host"},
                                          {"piping_id": self.pips[2].id, "title": "Inst_ts",
                                            "compute_resource_name": "host"}])}]}})

        plg_instances_count = PluginInstance.objects.count()
        with mock.patch.object(run_plugin_instance, 'delay',
                               return_value=None) as delay_mock:
            self.client.login(username=self.username, password=self.password)
            response = self.client.post(self.create_read_url, data=post,
                                        content_type=self.content_type)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(PluginInstance.objects.count(), plg_instances_count + 3)

            inst_ds1 = PluginInstance.objects.get(title="Inst_ds1")
            inst_ds2 = PluginInstance.objects.get(title="Inst_ds2")
            inst_ts = PluginInstance.objects.get(title="Inst_ts")
            param = inst_ts.string_param.filter(
                plugin_param__name='plugininstances').first()
            parent_ids = [int(parent_id) for parent_id in param.value.split(',')]
            for inst_id in parent_ids:
                self.assertIn(inst_id, [inst_ds1.id, inst_ds2.id])

    def test_workflow_list_success(self):
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        Workflow.objects.get_or_create(title='Workflow1', pipeline=pipeline, owner=owner)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, 'Workflow1')

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
        Workflow.objects.get_or_create(pipeline=pipeline, owner=owner)
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
        (workflow, tf) = Workflow.objects.get_or_create(
            title='Workflow2', pipeline=pipeline, owner=owner)
        self.read_update_delete_url = reverse("workflow-detail",
                                              kwargs={"pk": workflow.id})

    def test_workflow_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, 'Workflow2')

    def test_workflow_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_workflow_update_success(self):
        put = json.dumps({
            "template": {"data": [{"name": "title", "value": "Workflow3"}]}})

        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=put,
                                   content_type=self.content_type)
        self.assertContains(response, "Workflow3")

    def test_workflow_update_failure_unauthenticated(self):
        put = json.dumps({
            "template": {"data": [{"name": "title", "value": "Workflow3"}]}})

        response = self.client.put(self.read_update_delete_url, data=put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_workflow_update_failure_access_denied(self):
        put = json.dumps({
            "template": {"data": [{"name": "title", "value": "Workflow3"}]}})

        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_workflow_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Workflow.objects.count(), 0)

    def test_workflow_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_workflow_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class WorkflowPluginInstanceListViewTests(ViewTests):
    """
    Test the workflow-plugininstance-list view.
    """

    def setUp(self):
        super(WorkflowPluginInstanceListViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        owner = User.objects.get(username=self.username)
        (workflow, tf) = Workflow.objects.get_or_create(title='Workflow4',
                                                        pipeline=pipeline, owner=owner)
        self.list_url = reverse("workflow-plugininstance-list", kwargs={"pk": workflow.id})

    def test_workflow_plugin_instance_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_workflow_plugin_instance_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
