
import logging
import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from rest_framework import status

from plugins.models import Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter
from plugins.models import DefaultStrParameter, DefaultBoolParameter
from plugins.models import DefaultFloatParameter, DefaultIntParameter
from pipelines.models import Pipeline, PluginPiping


class ViewTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.content_type = 'application/vnd.collection+json'

        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'dummyInt': {'type': 'integer', 'optional': True,
                                                  'default': 111111}}
        self.username = 'foo'
        self.password = 'foo-pass'
        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create plugin
        (plugin_ds, tf) = Plugin.objects.get_or_create(name=self.plugin_ds_name,
                                                       type='ds',
                                                       compute_resource=self.compute_resource)
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
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PipelineViewTests(ViewTests):
    """
    Generic tests for pipeline views.
    """

    def setUp(self):
        super(PipelineViewTests, self).setUp()


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

        plugin_tree = '[{"plugin_id": ' + str(plugin_ds1.id) + \
                         ', "previous_index": null}, {"plugin_id": ' + \
                         str(plugin_ds2.id) + ', "previous_index": 0}]'
        post = json.dumps(
            {"template": {"data": [{"name": "name", "value": "Pipeline2"},
                                   {"name": "plugin_tree", "value": plugin_tree}]}})

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


class PipelineDefaultParameterListViewTests(PipelineViewTests):
    """
    Test the pipeline-defaultparameter-list view.
    """

    def setUp(self):
        super(PipelineDefaultParameterListViewTests, self).setUp()
        self.pipeline = Pipeline.objects.get(name="Pipeline1")
        self.list_url = reverse("pipeline-defaultparameter-list",
                                kwargs={"pk": self.pipeline.id})

    def test_pipeline_default_parameter_list_success(self):
        plugin_ds = Plugin.objects.get(name=self.plugin_ds_name)
        param = plugin_ds.parameters.get(name='dummyInt')
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, self.pips[0].id)
        self.assertContains(response, self.pips[1].id)
        self.assertContains(response, param.name)
        self.assertContains(response, plugin_ds.name)
        self.assertContains(response, 111111)

    def test_pipeline_default_parameter_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginPipingDetailViewTests(PipelineViewTests):
    """
    Test the pluginpiping-detail view.
    """

    def setUp(self):
        super(PluginPipingDetailViewTests, self).setUp()

        self.read_url = reverse("pluginpiping-detail", kwargs={"pk": self.pips[0].id})

    def test_plugin_piping_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "plugin_id")
        self.assertContains(response, "pipeline_id")

    def test_plugin_piping_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DefaultPipingStrParameterDetailViewTests(ViewTests):
    """
    Test the defaultpipingstrparameter-detail view.
    """

    def setUp(self):
        super(DefaultPipingStrParameterDetailViewTests, self).setUp()

        plugin_ds = Plugin.objects.get(name=self.plugin_ds_name)
        # add a parameter with a default
        (plg_param_ds, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyStr',
            type='string',
            optional=True
        )
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_ds,
                                                  value='test')  # set plugin parameter default
        pipeline = Pipeline.objects.get(name="Pipeline1")
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds,
                                                       pipeline=pipeline, previous=self.pips[1])
        default_param = pip.string_param.get(plugin_piping=pip)
        self.read_update_url = reverse("defaultpipingstrparameter-detail", kwargs={"pk": default_param.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "value", "value": "updated"}]}})

    def test_default_piping_str_parameter_detail_success_owner(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "test")
        #self.assertTrue(response.data["feed"].endswith(self.corresponding_feed_url))

    def test_default_piping_str_parameter_detail_failure_access_denied_pipeline_locked(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_default_piping_str_parameter_detail_success_pipeline_unlocked(self):
        pipeline = Pipeline.objects.get(name="Pipeline1")
        pipeline.locked = False
        pipeline.save()
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "test")

    def test_default_piping_str_parameter_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_piping_str_parameter_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "updated")

    def test_default_piping_str_parameter_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_piping_str_parameter_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DefaultPipingIntParameterDetailViewTests(ViewTests):
    """
    Test the defaultpipingintparameter-detail view.
    """

    def setUp(self):
        super(DefaultPipingIntParameterDetailViewTests, self).setUp()

        plugin_ds = Plugin.objects.get(name=self.plugin_ds_name)
        pipeline = Pipeline.objects.get(name="Pipeline1")
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds,
                                                       pipeline=pipeline, previous=self.pips[1])
        default_param = pip.integer_param.get(plugin_piping=pip)
        self.read_update_url = reverse("defaultpipingintparameter-detail", kwargs={"pk": default_param.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "value", "value": 222222}]}})

    def test_default_piping_int_parameter_detail_success_owner(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, 111111)

    def test_default_piping_int_parameter_detail_failure_access_denied_pipeline_locked(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_default_piping_int_parameter_detail_success_pipeline_unlocked(self):
        pipeline = Pipeline.objects.get(name="Pipeline1")
        pipeline.locked = False
        pipeline.save()
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, 111111)

    def test_default_piping_int_parameter_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_piping_int_parameter_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, 222222)

    def test_default_piping_int_parameter_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_piping_int_parameter_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DefaultPipingFloatParameterDetailViewTests(ViewTests):
    """
    Test the defaultpipingfloatparameter-detail view.
    """

    def setUp(self):
        super(DefaultPipingFloatParameterDetailViewTests, self).setUp()

        plugin_ds = Plugin.objects.get(name=self.plugin_ds_name)
        # add a parameter with a default
        (plg_param_ds, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyFloat',
            type='float',
            optional=True
        )
        DefaultFloatParameter.objects.get_or_create(plugin_param=plg_param_ds,
                                                  value=1.11111)  # set plugin parameter default
        pipeline = Pipeline.objects.get(name="Pipeline1")
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds,
                                                       pipeline=pipeline, previous=self.pips[1])
        default_param = pip.float_param.get(plugin_piping=pip)
        self.read_update_url = reverse("defaultpipingfloatparameter-detail", kwargs={"pk": default_param.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "value", "value": 1.22222}]}})

    def test_default_piping_float_parameter_detail_success_owner(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, 1.11111)

    def test_default_piping_float_parameter_detail_failure_access_denied_pipeline_locked(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_default_piping_float_parameter_detail_success_pipeline_unlocked(self):
        pipeline = Pipeline.objects.get(name="Pipeline1")
        pipeline.locked = False
        pipeline.save()
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, 1.11111)

    def test_default_piping_float_parameter_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_piping_float_parameter_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, 1.22222)

    def test_default_piping_float_parameter_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_piping_float_parameter_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DefaultPipingBoolParameterDetailViewTests(ViewTests):
    """
    Test the defaultpipingboolparameter-detail view.
    """

    def setUp(self):
        super(DefaultPipingBoolParameterDetailViewTests, self).setUp()

        plugin_ds = Plugin.objects.get(name=self.plugin_ds_name)
        # add a parameter with a default
        (plg_param_ds, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyBool',
            type='boolean',
            optional=True
        )
        DefaultBoolParameter.objects.get_or_create(plugin_param=plg_param_ds,
                                                  value=False)  # set plugin parameter default
        pipeline = Pipeline.objects.get(name="Pipeline1")
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds,
                                                       pipeline=pipeline, previous=self.pips[1])
        default_param = pip.boolean_param.get(plugin_piping=pip)
        self.read_update_url = reverse("defaultpipingboolparameter-detail", kwargs={"pk": default_param.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "value", "value": "true"}]}})

    def test_default_piping_bool_parameter_detail_success_owner(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "false")

    def test_default_piping_bool_parameter_detail_failure_access_denied_pipeline_locked(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_default_piping_bool_parameter_detail_success_pipeline_unlocked(self):
        pipeline = Pipeline.objects.get(name="Pipeline1")
        pipeline.locked = False
        pipeline.save()
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "false")

    def test_default_piping_bool_parameter_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_piping_bool_parameter_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "true")

    def test_default_piping_bool_parameter_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_piping_bool_parameter_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
