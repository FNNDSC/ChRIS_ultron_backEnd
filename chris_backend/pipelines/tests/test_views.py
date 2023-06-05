
import logging
import json
import io

from django.test import TestCase, tag
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import status

from plugins.models import PluginMeta, Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter
from plugins.models import DefaultStrParameter, DefaultBoolParameter
from plugins.models import DefaultFloatParameter, DefaultIntParameter
from pipelines.models import Pipeline, PluginPiping, DefaultPipingStrParameter

from core.storage import connect_storage


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class ViewTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.content_type = 'application/vnd.collection+json'

        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'dummyInt': {'type': 'integer', 'optional': True,
                                                  'default': 111111}}
        self.username = 'foo'
        self.password = 'foo-pass'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create plugin
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

        self.plugin_ts_name = "ts_copy"
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ts_name, type='ts')
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

        # create two plugin pipings
        self.pips = []
        (pip, tf) = PluginPiping.objects.get_or_create(title='pip1', plugin=plugin_ds,
                                                       pipeline=pipeline)
        self.pips.append(pip)
        (pip, tf) = PluginPiping.objects.get_or_create(title='pip2', plugin=plugin_ds,
                                                       previous=pip, pipeline=pipeline)
        self.pips.append(pip)

        # create another user
        self.other_username = 'boo'
        self.other_password = 'far'
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


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
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_convert', type='ds')
        (plugin_ds1, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds1.compute_resources.set([self.compute_resource])
        plugin_ds1.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

        plugin_tree = '[{"title": "pip5", "plugin_id": ' + str(plugin_ds1.id) + \
                      ', "previous": null}, {"title": "pip6", "plugin_id": ' + \
                      str(plugin_ds2.id) + ', "previous": "pip5"}]'
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

    def test_pipeline_list_success_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertNotContains(response, "Pipeline1")


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

    def test_plugin_list_query_search_success_unauthenticated(self):

        owner = User.objects.get(username=self.username)
        Pipeline.objects.get_or_create(name='Pipeline2', owner=owner,
                                       category='test', locked=False)
        list_url = reverse("pipeline-list-query-search") + '?category=test'
        response = self.client.get(list_url)
        self.assertNotContains(response, "Pipeline1")
        self.assertContains(response, "Pipeline2")


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

    def test_pipeline_detail_locked_failure_unauthenticated(self):
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


class PipelineCustomJsonDetailViewTests(PipelineViewTests):
    """
    Test the pipeline-customjson-detail view.
    """

    def setUp(self):
        super(PipelineCustomJsonDetailViewTests, self).setUp()
        pipeline = Pipeline.objects.get(name="Pipeline1")
        self.read_url = reverse("pipeline-detail", kwargs={"pk": pipeline.id})

    def test_pipeline_json_detail_success(self):
        owner = User.objects.get(username=self.username)
        # create a pipeline
        (pipeline_ts, tf) = Pipeline.objects.get_or_create(name='Pipeline_ts',
                                                        owner=owner, category='test')
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='ts_mycopy', type='ts')
        (plugin_ts, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ts.compute_resources.set([self.compute_resource])
        plugin_ts.save()
        # add a parameter with a default
        (plg_param_ts, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_ts,
            name='plugininstances',
            type='string',
            optional=True
        )
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_ts,
                                                  value="")  # set plugin parameter default

        # create plugin pipings
        (pip_ds1, tf) = PluginPiping.objects.get_or_create(title='pip1',
                                                           plugin=plugin_ds,
                                                           pipeline=pipeline_ts)
        (pip_ds2, tf) = PluginPiping.objects.get_or_create(title='pip2',
                                                           plugin=plugin_ds,
                                                           previous=pip_ds1,
                                                           pipeline=pipeline_ts)
        (pip_ts, tf) = PluginPiping.objects.get_or_create(title='pip3',
                                                          plugin=plugin_ts,
                                                          previous=pip_ds1,
                                                          pipeline=pipeline_ts)
        (default, tf) = DefaultPipingStrParameter.objects.get_or_create(plugin_param=plg_param_ts,
                                                                        plugin_piping=pip_ts)  # set piping's parameter default
        default.value = f"{pip_ds1.id},{pip_ds2.id}"
        default.save()

        read_url = reverse("pipeline-customjson-detail", kwargs={"pk": pipeline_ts.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, "Pipeline_ts")
        self.assertContains(response, "plugininstances")
        self.assertContains(response, "pip1")

    def test_pipeline_detail_locked_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PipelineSourceFileViewTests(PipelineViewTests):
    """
    Test the pipelinesourcefile-list view.
    """

    def setUp(self):
        super(PipelineSourceFileViewTests, self).setUp()
        self.create_read_url = reverse("pipelinesourcefile-list")
        self.pipeline_str = """
        name: TestPipeline
        locked: false
        plugin_tree:
        - title: simpledsapp1
          plugin: simpledsapp v0.1
          previous: ~
        - title: simpledsapp2
          plugin: simpledsapp v0.1
          previous: simpledsapp1
        - title: join
          plugin: ts_copy v0.1
          previous: simpledsapp1
          plugin_parameter_defaults:
            plugininstances: simpledsapp1,simpledsapp2
        """

    def tearDown(self):
        super(PipelineSourceFileViewTests, self).tearDown()

    @tag('integration')
    def test_integration_pipelinesourcefile_create_success(self):

        # POST request using multipart/form-data to be able to upload file
        self.client.login(username=self.username, password=self.password)

        with io.BytesIO(self.pipeline_str.encode()) as f:
            f.name = 'test_pipeline0000001.yaml'
            post = {"fname": f}
            response = self.client.post(self.create_read_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        fpath = f'PIPELINES/{self.username}/test_pipeline0000001.yaml'
        # delete file from Swift storage
        swift_manager = connect_storage(settings)
        swift_manager.delete_obj(fpath)

    def test_pipelinesourcefile_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data={"fname": {}})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


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
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_convert', type='ds')
        (plugin_ds1, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds1.compute_resources.set([self.compute_resource])
        plugin_ds1.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_analyze', type='ds')
        (plugin_ds2, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds2.compute_resources.set([self.compute_resource])
        plugin_ds2.save()

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
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_convert', type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

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
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        param = plugin_ds.parameters.get(name='dummyInt')
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, self.pips[0].id)
        self.assertContains(response, self.pips[1].id)
        self.assertContains(response, param.name)
        self.assertContains(response, plugin_ds.meta.name)
        self.assertContains(response, 111111)

    def test_pipeline_default_parameter_list_failure_locked__unauthenticated(self):
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

        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
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

        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
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

        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
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

        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
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
