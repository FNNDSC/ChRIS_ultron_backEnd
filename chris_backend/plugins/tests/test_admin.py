
import logging
import io
import json
from unittest import mock
from unittest.mock import ANY

from django.test import TestCase
from django import forms
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status

from plugins import admin as pl_admin


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class ComputeResourceAdminTests(TestCase):
    """
    Test ComputeResourceAdmin.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_add_view(self):
        """
        Test whether overriden add_view view only shows the proper fields in
        the add compute resource page and in editable mode.
        """
        compute_resource_admin = pl_admin.ComputeResourceAdmin(pl_admin.ComputeResource,
                                                               pl_admin.admin.site)
        request_mock = mock.Mock()
        with mock.patch.object(pl_admin.admin.ModelAdmin, 'add_view',
                               return_value=None) as add_view_mock:
            compute_resource_admin.add_view(request_mock)
            self.assertIn('name', compute_resource_admin.fields)
            self.assertIn('description', compute_resource_admin.fields)
            self.assertNotIn('creation_date', compute_resource_admin.fields)
            self.assertNotIn('modification_date', compute_resource_admin.fields)
            add_view_mock.assert_called_with(compute_resource_admin, request_mock,
                                             '', None)

    def test_change_view(self):
        """
        Test whether overriden change_view view shows all compute resource fields and
        the proper read-only and editable fields.
        """
        compute_resource_admin = pl_admin.ComputeResourceAdmin(pl_admin.ComputeResource,
                                                               pl_admin.admin.site)
        request_mock = mock.Mock()
        with mock.patch.object(pl_admin.admin.ModelAdmin, 'change_view',
                               return_value=None) as change_view_mock:
            compute_resource_admin.change_view(request_mock, 1)
            self.assertIn('name', compute_resource_admin.fields)
            self.assertIn('description', compute_resource_admin.fields)
            self.assertIn('creation_date', compute_resource_admin.fields)
            self.assertIn('modification_date', compute_resource_admin.fields)
            self.assertIn('creation_date', compute_resource_admin.readonly_fields)
            self.assertIn('modification_date', compute_resource_admin.readonly_fields)
            change_view_mock.assert_called_with(compute_resource_admin, request_mock, 1,
                                                '', None)

    def test_save_model(self):
        """
        Test whether overriden save_model method creates a new compute resource from the
        fields in the add compute resource page or properly change the modification date
        for a modified existing compute resource.
        """
        compute_resource_admin = pl_admin.ComputeResourceAdmin(pl_admin.ComputeResource,
                                                               pl_admin.admin.site)
        request_mock = mock.Mock()
        obj_mock = mock.Mock()
        obj_mock_creation_date = timezone.now()
        obj_mock.modification_date = obj_mock_creation_date
        form_mock = mock.Mock()
        form_mock.instance = mock.Mock()
        with mock.patch.object(pl_admin.admin.ModelAdmin, 'save_model',
                               return_value=None) as save_model_mock:
            compute_resource_admin.save_model(request_mock, obj_mock, form_mock, False)
            save_model_mock.assert_called_with(request_mock, obj_mock,
                                               form_mock, False)

            compute_resource_admin.save_model(request_mock, obj_mock, form_mock, True)
            save_model_mock.assert_called_with(request_mock, obj_mock, form_mock, True)
            self.assertGreater(obj_mock.modification_date, obj_mock_creation_date)

    def test_delete_model(self):
        """
        Test whether overriden delete_model method sets an error message when the user
        attempts to delete a compute resource that would result in orphan plugins.
        """
        (compute_resource, tf) = pl_admin.ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plg, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plg.compute_resources.set([compute_resource])
        plg.save()
        compute_resource_admin = pl_admin.ComputeResourceAdmin(pl_admin.ComputeResource,
                                                               pl_admin.admin.site)
        request_mock = mock.Mock()
        pl_admin.messages.set_level = mock.Mock(return_value=None)
        pl_admin.messages.error = mock.Mock(return_value=None)
        compute_resource_admin.delete_model(request_mock, compute_resource)
        pl_admin.messages.set_level.assert_called_with(request_mock, pl_admin.messages.ERROR)
        pl_admin.messages.error.assert_called_with(request_mock, ANY)

    def test_delete_queryset(self):
        """
        Test whether overriden delete_queryset method sets an error message when the user
        attempts to delete compute resources that would result in orphan plugins.
        """
        (compute_resource, tf) = pl_admin.ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plg, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plg.compute_resources.set([compute_resource])
        plg.save()
        compute_resource_admin = pl_admin.ComputeResourceAdmin(pl_admin.ComputeResource,
                                                               pl_admin.admin.site)
        request_mock = mock.Mock()
        pl_admin.messages.set_level = mock.Mock(return_value=None)
        pl_admin.messages.error = mock.Mock(return_value=None)
        compute_resource_admin.delete_queryset(request_mock, plg.compute_resources.all())
        pl_admin.messages.set_level.assert_called_with(request_mock, pl_admin.messages.ERROR)
        pl_admin.messages.error.assert_called_with(request_mock, ANY)


class PluginAdminFormTests(TestCase):
    """
    Test PluginAdminForm.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # re-enable logging
        logging.disable(logging.NOTSET)

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        (self.compute_resource, tf) = pl_admin.ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)
        # create a plugin
        self.plugin_name = "simplecopyapp"
        self.plugin_version = "0.1"
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                                  type='fs')
        self.plugin = pl_admin.Plugin()
        self.plugin.meta = pl_meta
        self.plugin.version = self.plugin_version

    def test_clean_validate_name_version_and_save_plugin_descriptors(self):
        """
        Test whether overriden clean method validates the full set of plugin descriptors
        and save the newly created plugin to the DB.
        """
        # mock manager's register_plugin method
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                                  type='fs')
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta,
                                                             version=self.plugin_version)
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()
        with mock.patch.object(pl_admin.PluginManager, 'register_plugin',
                               return_value=plugin) as register_plugin_mock:
            plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
            form = plugin_admin.form
            form.instance = self.plugin
            form.cleaned_data = {'name': self.plugin_name, 'version': self.plugin_version,
                                 'compute_resources': [self.compute_resource]}
            self.assertIsNone(form.instance.pk)
            form.clean(form)
            self.assertEqual(form.instance, plugin)
            self.assertIsNotNone(form.instance.pk)
            register_plugin_mock.assert_called_with(self.plugin_name,
                                                    self.plugin_version,
                                                    'host')

    def test_clean_validate_url_and_save_plugin_descriptors(self):
        """
        Test whether overriden clean method validates the full set of plugin descriptors
        and save the newly created plugin to the DB.
        """
        # mock manager's register_plugin_by_url method
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                                  type='fs')
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta,
                                                             version=self.plugin_version)
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()

        plugin_store_url = "http://chris-store.local:8010/api/v1/1/"
        with mock.patch.object(pl_admin.PluginManager, 'register_plugin_by_url',
                               return_value=plugin) as register_plugin_by_url_mock:
            plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
            form = plugin_admin.form
            form.instance = self.plugin
            form.cleaned_data = {'url': plugin_store_url,
                                 'compute_resources': plugin.compute_resources.all()}
            self.assertIsNone(form.instance.pk)
            form.clean(form)
            self.assertEqual(form.cleaned_data.get('name'), self.plugin_name)
            self.assertEqual(form.cleaned_data.get('version'), self.plugin_version)
            self.assertNotIn('url', form.cleaned_data)
            self.assertEqual(form.instance, plugin)
            self.assertIsNotNone(form.instance.pk)
            register_plugin_by_url_mock.assert_called_with(plugin_store_url, 'host')

    def test_clean_raises_validation_error_if_cannot_register_plugin(self):
        """
        Test whether overriden clean method raises a ValidationError when there
        is a validation error or it cannot save a new plugin to the DB.
        """
        # mock manager's register_plugin method
        with mock.patch.object(pl_admin.PluginManager, 'register_plugin',
                               side_effect=Exception) as register_plugin_mock:
            plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
            form = plugin_admin.form
            form.instance = self.plugin
            form.cleaned_data = {'name': self.plugin_name, 'version': self.plugin_version,
                                 'compute_resources': [self.compute_resource]}
            self.assertIsNone(form.instance.pk)
            with self.assertRaises(forms.ValidationError):
                form.clean(form)

    def test_clean_raises_validation_error_if_compute_resources_is_NONE(self):
        """
        Test whether overriden clean method raises a ValidationError when compute
        resources is None (the user didn't picked up any in the UI) .
        """
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name='test_plg',
                                                                  type='fs')
        plugin = pl_admin.Plugin()
        plugin.meta = pl_meta
        plugin.version = self.plugin_version
        # mock manager's register_plugin method
        with mock.patch.object(pl_admin.PluginManager, 'register_plugin',
                               return_value=plugin) as register_plugin_mock:
            plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
            form = plugin_admin.form
            form.instance = plugin
            form.cleaned_data = {'name': 'test_plg', 'version': self.plugin_version,
                                 'compute_resources': None}
            with self.assertRaises(forms.ValidationError):
                form.clean(form)


class PluginAdminTests(TestCase):
    """
    Test PluginAdmin.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_add_view(self):
        """
        Test whether overriden add_view view only shows the required fields in the add
        plugin page and in editable mode.
        """
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        request_mock = mock.Mock()
        with mock.patch.object(pl_admin.admin.ModelAdmin, 'add_view',
                               return_value=None) as add_view_mock:
            plugin_admin.add_view(request_mock)
            self.assertEqual(len(plugin_admin.fieldsets), 3)
            self.assertEqual(len(plugin_admin.readonly_fields), 0)
            add_view_mock.assert_called_with(plugin_admin, request_mock, '', None)

    def test_change_view(self):
        """
        Test whether overriden change_view view shows all plugin fields in readonly
        mode except the 'compute_resources' field that is shown in editable mode.
        """
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        request_mock = mock.Mock()
        with mock.patch.object(pl_admin.admin.ModelAdmin, 'change_view',
                               return_value=None) as change_view_mock:
            plugin_admin.change_view(request_mock, 1)
            self.assertNotIn('compute_resources', plugin_admin.readonly_fields)
            self.assertEqual(len(plugin_admin.fieldsets), 2)
            change_view_mock.assert_called_with(plugin_admin, request_mock, 1, '', None)

    def test_delete_model(self):
        """
        Test whether overriden delete_model method deletes the associated meta if this
        is the last associated plugin.
        """
        (compute_resource, tf) = pl_admin.ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plg, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plg.compute_resources.set([compute_resource])
        plg.save()
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        request_mock = mock.Mock()
        plugin_admin.delete_model(request_mock, plg)
        with self.assertRaises(pl_admin.PluginMeta.DoesNotExist):
            pl_admin.PluginMeta.objects.get(name='pacspull')

    def test_delete_queryset(self):
        """
        Test whether overriden delete_queryset method deletes plugin metas if their last
        associated plugin is deleted.
        """
        (compute_resource, tf) = pl_admin.ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plg, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plg.compute_resources.set([compute_resource])
        plg.save()
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        request_mock = mock.Mock()
        plugin_admin.delete_queryset(request_mock, pl_meta.plugins.all())
        with self.assertRaises(pl_admin.PluginMeta.DoesNotExist):
            pl_admin.PluginMeta.objects.get(name='pacspull')

    def test_add_plugins_from_file_view(self):
        """
        Test whether custom add_plugins_from_file_view view passes a summary dict in
        the context for valid form POST or otherwise an empty form.
        """
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        summary = {'success': [{'plugin_name': 'my_plugin'}], 'error': []}
        plugin_admin.register_plugins_from_file = mock.Mock(return_value=summary)
        request_mock = mock.Mock()
        request_mock.META = {'SCRIPT_NAME': ''}

        with mock.patch.object(pl_admin, 'render',
                               return_value=mock.Mock()) as render_mock:
            request_mock.method = 'GET'
            plugin_admin.add_plugins_from_file_view(request_mock)
            render_mock.assert_called_with(request_mock,
                                           'admin/plugins/plugin/add_plugins_from_file.html',
                                           {'site_title': 'ChRIS Admin',
                                            'site_header': 'ChRIS Administration',
                                            'site_url': ANY,
                                            'has_permission': ANY,
                                            'available_apps': ANY,
                                            'is_popup': ANY,
                                            'opts': ANY,
                                            'file_form': ANY})

            request_mock.method = 'POST'
            request_mock.FILES = {'file': 'f'}
            with mock.patch.object(pl_admin.UploadFileForm, 'is_valid',
                                   return_value=True) as is_valid_mock:
                plugin_admin.add_plugins_from_file_view(request_mock)
                plugin_admin.register_plugins_from_file.assert_called_with(
                    request_mock.FILES['file'])
                render_mock.assert_called_with(request_mock,
                                'admin/plugins/plugin/add_plugins_from_file_result.html',
                                               {'site_title': 'ChRIS Admin',
                                                'site_header': 'ChRIS Administration',
                                                'site_url': ANY,
                                                'has_permission': ANY,
                                                'available_apps': ANY,
                                                'is_popup': ANY,
                                                'opts': ANY,
                                                'summary': summary})

    def test_register_plugins_from_file(self):
        """
        Test whether custom register_plugins_from_file method registers plugins from the
        ChRIS store that have been specified in a text file.
        """
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        file_content = b'simplefsapp host\n simpledsapp 1.0.6 host\n http://chris-store.local:8010/api/v1/1/ host\n'

        with mock.patch.object(pl_admin.PluginManager, 'register_plugin',
                               return_value=None) as register_plugin_mock:

            with mock.patch.object(pl_admin.PluginManager, 'register_plugin_by_url',
                                   return_value=None) as register_plugin_by_url_mock:
                summary = {'success': [{'plugin_name': 'simplefsapp'},
                                       {'plugin_name': 'simpledsapp'},
                                       {'plugin_name': 'http://chris-store.local:8010/api/v1/1/'}
                                       ],
                           'error': []}
                with io.BytesIO(file_content) as f:
                    self.assertEqual(plugin_admin.register_plugins_from_file(f), summary)
                    register_plugin_mock.assert_called_with('simpledsapp', '1.0.6', 'host')
                    register_plugin_by_url_mock.assert_called_with('http://chris-store.local:8010/api/v1/1/',
                                                              'host')

            with mock.patch.object(pl_admin.PluginManager, 'register_plugin_by_url',
                                   side_effect=Exception('Error')):
                summary = {'success': [{'plugin_name': 'simplefsapp'},
                                       {'plugin_name': 'simpledsapp'}
                                       ],
                           'error': [{'plugin_name': 'http://chris-store.local:8010/api/v1/1/',
                                      'code': 'Error'}]}
                with io.BytesIO(file_content) as f:
                    self.assertEqual(plugin_admin.register_plugins_from_file(f), summary)


class ComputeResourceAdminListViewTests(PluginAdminFormTests):
    """
    Test the admin-computeresource-list.
    """

    def setUp(self):
        super(ComputeResourceAdminListViewTests, self).setUp()

        self.content_type = 'application/vnd.collection+json'
        self.create_read_url = reverse("admin-computeresource-list")
        self.post = json.dumps(
            {"template": {"data": [{"name": "name",
                                    "value": "moc"},
                                   {"name": "compute_url",
                                    "value": "http://pfcon.local:30005/api/v1/1/"},
                                   {"name": "description",
                                    "value": "moc compute env"}
                                   ]}})
        self.admin_username = 'admin'
        self.admin_password = 'adminpass'
        self.username = 'foo'
        self.password = 'pass'
        # create admin user
        User.objects.create_superuser(username=self.admin_username,
                                      password=self.admin_password,
                                      email='admin@babymri.org')
        # create normal user
        User.objects.create_user(username=self.username,
                                 password=self.password)

    def test_compute_resource_create_success(self):
        self.client.login(username=self.admin_username, password=self.admin_password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_compute_resource_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_compute_resource_create_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_compute_resource_list_success(self):
        self.client.login(username=self.admin_username, password=self.admin_password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, self.compute_resource.name)

    def test_compute_resource_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_compute_resource_list_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PluginAdminSerializerTests(PluginAdminFormTests):

    def test_validate_registers_plugin(self):
        """
        Test whether overriden validate method registers plugin by url.
        """
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                                  type='fs')
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta,
                                                             version=self.plugin_version)
        # mock manager's register_plugin_by_url method
        plugin_store_url = "http://chris-store.local:8010/api/v1/1/"
        with mock.patch.object(pl_admin.PluginManager, 'register_plugin_by_url',
                               return_value=plugin) as register_plugin_by_url_mock:
            plg_admin_serializer = pl_admin.PluginAdminSerializer(plugin)
            data = {'plugin_store_url': plugin_store_url,
                    'compute_name': self.compute_resource.name}
            data = plg_admin_serializer.validate(data)
            self.assertNotIn('plugin_store_url', data)
            self.assertNotIn('compute_name', data)
            register_plugin_by_url_mock.assert_called_with(plugin_store_url,
                                                           self.compute_resource.name)

    def test_validate_raises_validation_error_if_cannot_register_plugin(self):
        """
        Test whether overriden validate method raises a ValidationError when there
        is a validation error or it cannot save a new plugin to the DB.
        """
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                                  type='fs')
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta,
                                                             version=self.plugin_version)
        # mock manager's register_plugin method
        with mock.patch.object(pl_admin.PluginManager, 'register_plugin_by_url',
                               side_effect=Exception) as register_plugin_by_url_mock:
            plg_admin_serializer = pl_admin.PluginAdminSerializer(plugin)
            plugin_store_url = "http://chris-store.local:8010/api/v1/1/"
            data = {'plugin_store_url': plugin_store_url,
                    'compute_name': self.compute_resource.name}
            with self.assertRaises(pl_admin.serializers.ValidationError):
                plg_admin_serializer.validate(data)


class PluginAdminListViewTests(PluginAdminFormTests):
    """
    Test the admin-plugin-list view.
    """

    def setUp(self):
        super(PluginAdminListViewTests, self).setUp()

        self.content_type = 'application/vnd.collection+json'
        self.create_read_url = reverse("admin-plugin-list")
        self.post = json.dumps(
            {"template": {"data": [{"name": "plugin_store_url",
                                    "value": "http://chris-store.local:8010/api/v1/1/"},
                                   {"name": "compute_name",
                                    "value": self.compute_resource.name}
                                   ]}})
        self.admin_username = 'admin'
        self.admin_password = 'adminpass'
        self.username = 'foo'
        self.password = 'pass'
        # create admin user
        User.objects.create_superuser(username=self.admin_username,
                                      password=self.admin_password,
                                      email='admin@babymri.org')
        # create normal user
        User.objects.create_user(username=self.username,
                                 password=self.password)

    def test_plugin_create_success(self):
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                                  type='fs')
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(meta=pl_meta,
                                                             version=self.plugin_version)
        self.client.login(username=self.admin_username, password=self.admin_password)
        with mock.patch.object(pl_admin.PluginManager, 'register_plugin_by_url',
                               return_value=plugin) as register_plugin_by_url_mock:
            response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_plugin_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_create_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_list_success(self):
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                                  type='fs')
        pl_admin.Plugin.objects.get_or_create(meta=pl_meta, version=self.plugin_version)
        self.client.login(username=self.admin_username, password=self.admin_password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, self.plugin_name)

    def test_plugin_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_list_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
