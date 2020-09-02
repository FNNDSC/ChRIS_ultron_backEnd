
import logging

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import status

from plugins.models import PluginMeta, Plugin
from plugins.models import PluginParameter, DefaultStrParameter
from plugins.models import ComputeResource


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class ViewTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.username = 'foo'
        self.password = 'bar'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create API user
        User.objects.create_user(username=self.username,
                                 password=self.password)

        # create an fs plugins
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='simplecopyapp', type='fs')
        (plugin_fs, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_fs.compute_resources.set([self.compute_resource])
        plugin_fs.save()
        # add plugin's parameters
        (plg_param, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type='string',
            optional=True
        )
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param, value="./")

        # create a ds plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_convert', type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class ComputeResourceListViewTests(ViewTests):
    """
    Test the computeresource-list view.
    """

    def setUp(self):
        super(ComputeResourceListViewTests, self).setUp()
        self.list_url = reverse("computeresource-list")

    def test_compute_resource_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, COMPUTE_RESOURCE_URL)

    def test_compute_resource_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ComputeResourceListQuerySearchViewTests(ViewTests):
    """
    Test the computeresource-list-query-search view.
    """

    def setUp(self):
        super(ComputeResourceListQuerySearchViewTests, self).setUp()
        self.list_url = reverse("computeresource-list-query-search") + '?name=host'

    def test_compute_resource_list_query_search_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, COMPUTE_RESOURCE_URL)

    def test_compute_resource_list_query_search_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ComputeResourceDetailViewTests(ViewTests):
    """
    Test the computeresource-detail view.
    """

    def setUp(self):
        super(ComputeResourceDetailViewTests, self).setUp()
        compute_resource = ComputeResource.objects.get(name="host")

        self.read_url = reverse("computeresource-detail", kwargs={"pk": compute_resource.id})

    def test_compute_resource_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, COMPUTE_RESOURCE_URL)

    def test_compute_resource_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginMetaListViewTests(ViewTests):
    """
    Test the pluginmeta-list view.
    """

    def setUp(self):
        super(PluginMetaListViewTests, self).setUp()
        self.list_url = reverse("pluginmeta-list")

    def test_plugin_meta_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, 'simplecopyapp')
        self.assertContains(response, 'mri_convert')

    def test_plugin_meta_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginMetaListQuerySearchViewTests(ViewTests):
    """
    Test the pluginmeta-list-query-search view.
    """

    def setUp(self):
        super(PluginMetaListQuerySearchViewTests, self).setUp()
        self.list_url = reverse("pluginmeta-list-query-search") + '?name=simplecopyapp'

    def test_plugin_meta_list_query_search_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, 'simplecopyapp')

    def test_plugin_meta_list_query_search_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginMetaPluginListViewTests(ViewTests):
    """
    Test the pluginmeta-plugin-list view.
    """

    def setUp(self):
        super(PluginMetaPluginListViewTests, self).setUp()

        pl_meta = PluginMeta.objects.get(name="simplecopyapp")
        self.list_url = reverse("pluginmeta-plugin-list", kwargs={"pk": pl_meta.id})

    def test_plugin_meta_plugin_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "simplecopyapp")
        self.assertNotContains(response, "mri_convert")  # plugin list is plugin meta-specific

    def test_plugin_compute_resource_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginMetaDetailViewTests(ViewTests):
    """
    Test the pluginmeta-detail view.
    """

    def setUp(self):
        super(PluginMetaDetailViewTests, self).setUp()

        meta = PluginMeta.objects.get(name='simplecopyapp')
        self.read_url = reverse("pluginmeta-detail", kwargs={"pk": meta.id})

    def test_plugin_meta_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'simplecopyapp')

    def test_plugin_meta_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


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
        self.assertContains(response, "simplecopyapp")
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
        self.list_url = reverse("plugin-list-query-search") + '?name=simplecopyapp'

    def test_plugin_list_query_search_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "simplecopyapp")
        self.assertNotContains(response, "mri_convert")

    def test_plugin_list_query_search_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginComputeResourceListViewTests(ViewTests):
    """
    Test the plugin-computeresource-list view.
    """

    def setUp(self):
        super(PluginComputeResourceListViewTests, self).setUp()

        plugin = Plugin.objects.get(meta__name="simplecopyapp")
        self.list_url = reverse("plugin-computeresource-list", kwargs={"pk": plugin.id})

    def test_plugin_compute_resource_list_success(self):
        ComputeResource.objects.get_or_create(name="new", compute_url=COMPUTE_RESOURCE_URL)
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, COMPUTE_RESOURCE_URL)
        self.assertNotContains(response, "new")  # compute resource list is plugin-specific

    def test_plugin_compute_resource_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginDetailViewTests(ViewTests):
    """
    Test the plugin-detail view.
    """

    def setUp(self):
        super(PluginDetailViewTests, self).setUp()
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='simplecopyapp', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')

        self.read_url = reverse("plugin-detail", kwargs={"pk": plugin.id})

    def test_plugin_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "simplecopyapp")

    def test_plugin_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PluginParameterListViewTests(ViewTests):
    """
    Test the pluginparameter-list view.
    """

    def setUp(self):
        super(PluginParameterListViewTests, self).setUp()
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='simplecopyapp', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')

        # self.corresponding_plugin_url = reverse("plugin-detail", kwargs={"pk": plugin.id})
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
        # get the plugin parameter
        param = PluginParameter.objects.get(name='dir')
        self.read_url = reverse("pluginparameter-detail", kwargs={"pk": param.id})

    def test_plugin_parameter_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, "dir")
        self.assertContains(response, "default")
        self.assertContains(response, "./")

    def test_plugin_parameter_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
