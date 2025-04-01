
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
from django.core.files.base import ContentFile
from rest_framework import status
from rest_framework import serializers

from plugins import admin as pl_admin
from plugins.models import PluginMeta, Plugin, PluginParameter



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
                                            'is_nav_sidebar_enabled': ANY,
                                            'log_entries': ANY,
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
                                                'is_nav_sidebar_enabled': ANY,
                                                'log_entries': ANY,
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
                                   {"name": "compute_user",
                                    "value": "mocuser"},
                                   {"name": "compute_password",
                                    "value": "mocuser1234"},
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


class ComputeResourceAdminDetailViewTests(PluginAdminFormTests):
    """
    Test the admin-computeresource-detail view.
    """

    def setUp(self):
        super(ComputeResourceAdminDetailViewTests, self).setUp()

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

        self.read_delete_url = reverse("admin-computeresource-detail",
                                       kwargs={"pk": self.compute_resource.id})

    def test_compute_resource_detail_success(self):
        self.client.login(username=self.admin_username, password=self.admin_password)
        response = self.client.get(self.read_delete_url)
        self.assertContains(response, 'host')

    def test_compute_resource_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_compute_resource_detail_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PluginAdminSerializerTests(PluginAdminFormTests):

    def setUp(self):
        super(PluginAdminSerializerTests, self).setUp()

        self.content_type = 'application/vnd.collection+json'
        self.create_read_url = reverse("admin-plugin-list")
        self.post = {'fname': '', 'compute_names': 'host'}
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

        plugin_parameters = [{'name': 'dir', 'type': str.__name__, 'action': 'store',
                              'optional': True, 'flag': '--dir', 'short_flag': '-d',
                              'default': '/', 'help': 'test plugin', 'ui_exposed': True}]

        self.plg_data = {'description': 'Dir test plugin',
                         'dock_image': 'fnndsc/pl-simplefsapp',
                         'version': self.plugin_version,
                         'execshell': 'python3',
                         'selfpath': '/usr/src/simplefsapp',
                         'selfexec': 'simplefsapp.py'}

        self.plg_meta_data = {'name': self.plugin_name,
                              'title': 'Dir plugin',
                              'license': 'MIT',
                              'type': 'fs',
                              'icon': 'http://github.com/plugin',
                              'category': 'Dir',
                              'authors': 'DEV FNNDSC'}

        self.plg_repr = self.plg_data.copy()
        self.plg_repr.update(self.plg_meta_data)
        self.plg_repr['parameters'] = plugin_parameters

        # create a plugin
        (meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_name)
        (plugin, tf) = Plugin.objects.get_or_create(meta=meta,
                                                    version=self.plg_repr['version'],
                                                    dock_image=self.plg_repr['dock_image'])

        # add plugin's parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=self.plg_repr['parameters'][0]['name'],
            type=self.plg_repr['parameters'][0]['type'],
            optional=self.plg_repr['parameters'][0]['optional'],
            action=self.plg_repr['parameters'][0]['action'],
            flag=self.plg_repr['parameters'][0]['flag'],
            short_flag=self.plg_repr['parameters'][0]['short_flag'],
        )
        param_names = plugin.get_plugin_parameter_names()
        self.assertEqual(param_names, [self.plg_repr['parameters'][0]['name']])

    def test_validate_app_version(self):
        """
        Test whether custom validate_app_version method raises a ValidationError when
        wrong version type or format has been submitted.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_app_version(1.2)
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_app_version('v1.2')

    def test_validate_meta_version(self):
        """
        Test whether custom validate_meta_version method raises a ValidationError when
        plugin meta and version are not unique together.
        """
        (meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer()
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_meta_version(meta, self.plg_repr['version'])

    def test_validate_meta_image(self):
        """
        Test whether custom validate_meta_image method raises a ValidationError when
        plugin meta and docker image are not unique together.
        """
        (meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer()
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_meta_image(meta, self.plg_repr['dock_image'])

    def test_create_also_creates_meta_first_time_plugin_name_is_used(self):
        """
        Test whether overriden create also creates a new plugin meta when creating a
        plugin with a new name that doesn't already exist in the system.
        """
        user = User.objects.get(username=self.username)
        validated_data = self.plg_repr.copy()
        validated_data['name'] = 'testapp'
        validated_data['parameters'][0]['type'] = 'string'
        validated_data['dock_image'] = 'fnndsc/pl-testapp'
        f = ContentFile(json.dumps(self.plg_repr).encode())
        f.name = 'testapp.json'
        validated_data['fname'] = f
        validated_data['compute_names'] = [self.compute_resource]
        plg_serializer = pl_admin.PluginAdminSerializer()
        with self.assertRaises(PluginMeta.DoesNotExist):
            PluginMeta.objects.get(name='testapp')
        plg_serializer.create(validated_data)
        self.assertEqual(PluginMeta.objects.get(name='testapp').name, 'testapp')

    def test_create_does_not_create_meta_after_first_time_plugin_name_is_used(self):
        """
        Test whether overriden create does not create a new plugin meta when creating a
        plugin version with a name that already exists in the system.
        """
        user = User.objects.get(username=self.username)
        validated_data = self.plg_repr.copy()
        validated_data['parameters'][0]['type'] = 'string'
        validated_data['version'] = '0.2.2'
        validated_data['dock_image'] = 'fnndsc/pl-testapp'
        f = ContentFile(json.dumps(self.plg_repr).encode())
        f.name = 'testapp.json'
        validated_data['fname'] = f
        validated_data['compute_names'] = [self.compute_resource]
        plg_serializer = pl_admin.PluginAdminSerializer()
        n_plg_meta = PluginMeta.objects.count()
        plg_meta = PluginMeta.objects.get(name=self.plugin_name)
        plugin = plg_serializer.create(validated_data)
        self.assertEqual(n_plg_meta, PluginMeta.objects.count())
        self.assertEqual(plugin.meta, plg_meta)

    def test_read_app_representation(self):
        """
        Test whether custom read_app_representation method returns an appropriate plugin
        representation dictionary from an uploaded json representation file.
        """
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            self.assertEqual(pl_admin.PluginAdminSerializer.read_app_representation(f),
                             self.plg_repr)

    def test_check_required_descriptor(self):
        """
        Test whether custom check_required_descriptor method raises a ValidationError
        when a required descriptor is missing from the plugin app representation.
        """
        del self.plg_repr['execshell']
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.check_required_descriptor(self.plg_repr,
                                                                     'execshell')

    def test_validate_app_descriptor_limits(self):
        """
        Test whether custom validate_app_descriptor_limit method raises a ValidationError
        when the max limit is smaller than the min limit.
        """
        self.plg_repr['min_cpu_limit'] = 200
        self.plg_repr['max_cpu_limit'] = 100
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_descriptor_limits(self.plg_repr,
                                                            'min_cpu_limit',
                                                            'max_cpu_limit')

    def test_validate_app_int_descriptor(self):
        """
        Test whether custom validate_app_int_descriptor method raises a ValidationError
        when the descriptor cannot be converted to a non-negative integer.
        """
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_int_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_int_descriptor(-1)

    def test_validate_app_gpu_descriptor(self):
        """
        Test whether custom validate_app_gpu_descriptor method raises a ValidationError
        when the gpu descriptor cannot be converted to a non-negative integer.
        """
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_gpu_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_gpu_descriptor(-1)

    def test_validate_app_workers_descriptor(self):
        """
        Test whether custom validate_app_workers_descriptor method raises a ValidationError
        when the app worker descriptor cannot be converted to a positive integer.
        """
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_workers_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_workers_descriptor(0)

    def test_validate_app_cpu_descriptor(self):
        """
        Test whether custom validate_app_cpu_descriptor method raises a ValidationError
        when the app cpu descriptor cannot be converted to a fields.CPUInt.
        """
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_cpu_descriptor('100me')
            self.assertEqual(100, pl_admin.PluginAdminSerializer.validate_app_cpu_descriptor('100m'))

    def test_validate_app_memory_descriptor(self):
        """
        Test whether custom validate_app_memory_descriptor method raises a ValidationError
        when the app memory descriptor cannot be converted to a fields.MemoryInt.
        """
        with self.assertRaises(serializers.ValidationError):
            pl_admin.PluginAdminSerializer.validate_app_cpu_descriptor('100me')
            self.assertEqual(100, pl_admin.PluginAdminSerializer.validate_app_cpu_descriptor('100mi'))
            self.assertEqual(100, pl_admin.PluginAdminSerializer.validate_app_cpu_descriptor('100gi'))

    def test_validate_app_parameters_type(self):
        """
        Test whether custom validate_app_parameters method raises a ValidationError when
        a plugin parameter has an unsupported type.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        parameter_list = self.plg_repr['parameters']
        parameter_list[0]['type'] = 'booleano'
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_app_parameters(parameter_list)

    def test_validate_app_parameters_default(self):
        """
        Test whether custom validate_app_parameters method raises a ValidationError when
        an optional plugin parameter doesn't have a default value specified.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        parameter_list = self.plg_repr['parameters']
        parameter_list[0]['default'] = None
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_app_parameters(parameter_list)

    def test_validate_app_parameters_of_path_type_and_optional(self):
        """
        Test whether custom validate_app_parameters method raises a ValidationError when
        a plugin parameter is optional anf of type 'path' or 'unextpath'.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        parameter_list = self.plg_repr['parameters']
        parameter_list[0]['type'] = 'path'
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_app_parameters(parameter_list)
        parameter_list[0]['type'] = 'unextpath'
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_app_parameters(parameter_list)

    def test_validate_app_parameters_not_ui_exposed_and_not_optional(self):
        """
        Test whether custom validate_app_parameters method raises a ValidationError when
        a plugin parameter that is not optional is not exposed to the ui.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        parameter_list = self.plg_repr['parameters']
        parameter_list[0]['optional'] = False
        parameter_list[0]['ui_exposed'] = False
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_app_parameters(parameter_list)

    def test_validate_check_required_execshell(self):
        """
        Test whether the custom validate method raises a ValidationError when required
        'execshell' descriptor is missing from the plugin app representation.
        """
        del self.plg_repr['execshell'] # remove required 'execshell' from representation
        plg_serializer = pl_admin.PluginAdminSerializer()
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_check_required_selfpath(self):
        """
        Test whether the custom validate method raises a ValidationError when required
        'selfpath' descriptor is missing from the plugin app representation.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        del self.plg_repr['selfpath'] # remove required 'selfpath' from representation
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_check_required_selfexec(self):
        """
        Test whether the custom validate method raises a ValidationError when required
        'selfexec' descriptor is missing from the plugin app representation.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        del self.plg_repr['selfexec'] # remove required 'selfexec' from representation
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_check_required_parameters(self):
        """
        Test whether the custom validate method raises a ValidationError when required
        'parameters' descriptor is missing from the plugin app representation.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        del self.plg_repr['parameters'] # remove required 'parameters' from representation
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_remove_empty_min_number_of_workers(self):
        """
        Test whether the custom validate method removes 'min_number_of_workers'
        descriptor from the validated data when it is the empty string.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        self.plg_repr['min_number_of_workers'] = ''
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            self.assertNotIn('min_number_of_workers', plg_serializer.validate(data))

    def test_validate_remove_empty_max_number_of_workers(self):
        """
        Test whether the custom validate method removes 'max_number_of_workers'
        descriptor from the validated data when it is the empty string.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        self.plg_repr['max_number_of_workers'] = ''
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            self.assertNotIn('max_number_of_workers', plg_serializer.validate(data))

    def test_validate_remove_empty_min_gpu_limit(self):
        """
        Test whether the custom validate method removes 'min_gpu_limit' descriptor from
        the validated data when it is the empty string.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        self.plg_repr['min_gpu_limit'] = ''
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            self.assertNotIn('min_gpu_limit', plg_serializer.validate(data))

    def test_validate_remove_empty_max_gpu_limit(self):
        """
        Test whether the custom validate method removes 'max_gpu_limit' descriptor from
        the validated data when it is the empty string.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        self.plg_repr['max_gpu_limit'] = ''
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            self.assertNotIn('max_gpu_limit', plg_serializer.validate(data))

    def test_validate_remove_empty_min_cpu_limit(self):
        """
        Test whether the custom validate method removes 'min_cpu_limit' descriptor from
        the validated data when it is the empty string.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        self.plg_repr['min_cpu_limit'] = ''
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            self.assertNotIn('min_cpu_limit', plg_serializer.validate(data))

    def test_validate_remove_empty_max_cpu_limit(self):
        """
        Test whether the custom validate method removes 'max_cpu_limit' descriptor from
        the validated data when it is the empty string.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        self.plg_repr['max_cpu_limit'] = ''
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            self.assertNotIn('max_cpu_limit', plg_serializer.validate(data))

    def test_validate_remove_empty_min_memory_limit(self):
        """
        Test whether the custom validate method removes 'min_memory_limit'
        descriptor from the validated data when it is the empty string.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        self.plg_repr['min_memory_limit'] = ''
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            self.assertNotIn('min_memory_limit', plg_serializer.validate(data))

    def test_validate_remove_empty_max_memory_limit(self):
        """
        Test whether the custom validate method removes 'max_memory_limit'
        descriptor from the validated data when it is the empty string.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = pl_admin.PluginAdminSerializer(plugin)
        self.plg_repr['max_memory_limit'] = ''
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            self.assertNotIn('max_memory_limit', plg_serializer.validate(data))

    def test_validate_workers_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_number_of_workers' is smaller than the 'min_number_of_workers'.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        self.plg_repr['min_number_of_workers'] = 2
        self.plg_repr['max_number_of_workers'] = 1
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_cpu_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_cpu_limit' is smaller than the 'min_cpu_limit'.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        self.plg_repr['min_cpu_limit'] = 200
        self.plg_repr['max_cpu_limit'] = 100
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_memory_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_memory_limit' is smaller than the 'min_memory_limit'.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        self.plg_repr['min_memory_limit'] = 100000
        self.plg_repr['max_memory_limit'] = 10000
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_gpu_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_gpu_limit' is smaller than the 'max_gpu_limit'.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        self.plg_repr['min_gpu_limit'] = 2
        self.plg_repr['max_gpu_limit'] = 1
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_validate_app_parameters(self):
        """
        Test whether custom validate method validates submitted plugin's parameters.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        parameter_list = self.plg_repr['parameters']
        parameter_list[0]['type'] = 'booleano'
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            with self.assertRaises(serializers.ValidationError):
                plg_serializer.validate(data)

    def test_validate_update_validated_data(self):
        """
        Test whether custom validate method updates validated data with the plugin app
        representation.
        """
        plg_serializer = pl_admin.PluginAdminSerializer()
        with io.BytesIO(json.dumps(self.plg_repr).encode()) as f:
            data = {'fname': f}
            new_data = plg_serializer.validate(data)
            self.assertIn('version', new_data)
            self.assertIn('execshell', new_data)
            self.assertIn('selfpath', new_data)
            self.assertIn('selfexec', new_data)
            self.assertIn('parameters', new_data)


class PluginAdminListViewTests(PluginAdminFormTests):
    """
    Test the admin-plugin-list view.
    """

    def setUp(self):
        super(PluginAdminListViewTests, self).setUp()

        self.create_read_url = reverse("admin-plugin-list")
        self.post = {'fname': '', 'compute_names': 'host'}
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

        plugin_parameters = [{'name': 'dir', 'type': str.__name__, 'action': 'store',
                              'optional': True, 'flag': '--dir', 'short_flag': '-d',
                              'default': '/', 'help': 'test plugin', 'ui_exposed': True}]

        self.plg_data = {'description': 'Dir test plugin',
                         'dock_image': 'fnndsc/pl-simplefsapp',
                         'version': self.plugin_version,
                         'execshell': 'python3',
                         'selfpath': '/usr/src/simplefsapp',
                         'selfexec': 'simplefsapp.py'}

        self.plg_meta_data = {'name': self.plugin_name,
                              'title': 'Dir plugin',
                              'license': 'MIT',
                              'type': 'fs',
                              'icon': 'http://github.com/plugin',
                              'category': 'Dir',
                              'authors': 'DEV FNNDSC'}

        self.plg_repr = self.plg_data.copy()
        self.plg_repr.update(self.plg_meta_data)
        self.plg_repr['parameters'] = plugin_parameters

    def test_plugin_create_success(self):
        with io.StringIO(json.dumps(self.plg_repr)) as f:
            post = self.post.copy()
            post["fname"] = f
            self.client.login(username=self.admin_username, password=self.admin_password)
            #  multipart request
            response = self.client.post(self.create_read_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_plugin_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_create_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post)
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


class PluginAdminDetailViewTests(PluginAdminFormTests):
    """
    Test the admin-plugin-detail view.
    """

    def setUp(self):
        super(PluginAdminDetailViewTests, self).setUp()

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

        # create a plugin
        (pl_meta, tf) = pl_admin.PluginMeta.objects.get_or_create(name='mytestcopyapp',
                                                                  type='fs')
        plugin = pl_admin.Plugin()
        plugin.meta = pl_meta
        plugin.version = '0.1'
        plugin.save()
        self.read_update_delete_url = reverse("admin-plugin-detail",
                                              kwargs={"pk": plugin.id})
        self.put = json.dumps({"template": {"data": [{"name": "compute_names",
                                                      "value": "host"}]}})
        self.content_type = 'application/vnd.collection+json'

    def test_plugin_detail_success(self):
        self.client.login(username=self.admin_username, password=self.admin_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, 'mytestcopyapp')

    def test_plugin_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_detail_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_update_success(self):
        self.client.login(username=self.admin_username, password=self.admin_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_plugin_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_update_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugin_delete_success(self):
        self.client.login(username=self.admin_username, password=self.admin_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Plugin.objects.count(), 0)

    def test_plugin_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_plugin_delete_failure_access_denied(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
