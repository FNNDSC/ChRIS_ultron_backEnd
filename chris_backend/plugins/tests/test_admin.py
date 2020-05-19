
import logging
import io
from unittest import mock
from unittest.mock import ANY

from django.test import TestCase
from django import forms
from django.utils import timezone

from plugins import admin as pl_admin


class ComputeResourceAdminTests(TestCase):
    """
    Test ComputeResourceAdmin.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # re-enable logging
        logging.disable(logging.DEBUG)

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
            name="host", description="host description")
        (plg, tf) = pl_admin.Plugin.objects.get_or_create(name="pacspull", type="fs")
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
            name="host", description="host description")
        (plg, tf) = pl_admin.Plugin.objects.get_or_create(name="pacspull", type="fs")
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
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # re-enable logging
        logging.disable(logging.DEBUG)

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        (self.compute_resource, tf) = pl_admin.ComputeResource.objects.get_or_create(
            name="host", description="host description")
        # create a plugin
        self.plugin_name = "simplecopyapp"
        self.plugin_version = "0.1"
        self.plugin = pl_admin.Plugin()
        self.plugin.name = self.plugin_name
        self.plugin.version = self.plugin_version

    def test_clean_validate_name_version_and_save_plugin_descriptors(self):
        """
        Test whether overriden clean method validates the full set of plugin descriptors
        and save the newly created plugin to the DB.
        """
        # mock manager's register_plugin method
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(
            name=self.plugin_name, version=self.plugin_version)
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
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(
            name=self.plugin_name, version=self.plugin_version)
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()

        plugin_store_url = "http://127.0.0.1:8010/api/v1/1/"
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


class PluginAdminTests(TestCase):
    """
    Test PluginAdmin.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # re-enable logging
        logging.disable(logging.DEBUG)

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

    def test_save_model(self):
        """
        Test whether overriden save_model method creates a plugin from the fields in
        the add plugin page or properly change the modification date for a modified
        existing plugin.
        """
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        request_mock = mock.Mock()
        obj_mock = mock.Mock()
        obj_mock_creation_date = timezone.now()
        obj_mock.modification_date = obj_mock_creation_date
        form_mock = mock.Mock()
        form_mock.instance = mock.Mock()
        with mock.patch.object(pl_admin.admin.ModelAdmin, 'save_model',
                               return_value=None) as save_model_mock:
            plugin_admin.save_model(request_mock, obj_mock, form_mock, False)
            save_model_mock.assert_called_with(request_mock, obj_mock,
                                               form_mock, False)

            plugin_admin.save_model(request_mock, obj_mock, form_mock, True)
            save_model_mock.assert_called_with(request_mock, obj_mock, form_mock, True)
            self.assertGreater(obj_mock.modification_date, obj_mock_creation_date)

    def test_register_plugins_from_file(self):
        """
        Test whether custom register_plugins_from_file method registers plugins from the
        ChRIS store that have been specified in a text file.
        """
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        file_content = b'simplefsapp host\n simpledsapp 1.0.6 host\n http://127.0.0.1:8010/api/v1/1/ host\n'

        with mock.patch.object(pl_admin.PluginManager, 'register_plugin',
                               return_value=None) as register_plugin_mock:

            with mock.patch.object(pl_admin.PluginManager, 'register_plugin_by_url',
                                   return_value=None) as register_plugin_by_url_mock:
                summary = {'success': [{'plugin_name': 'simplefsapp'},
                                       {'plugin_name': 'simpledsapp'},
                                       {'plugin_name': 'http://127.0.0.1:8010/api/v1/1/'}
                                       ],
                           'error': []}
                with io.BytesIO(file_content) as f:
                    self.assertEqual(plugin_admin.register_plugins_from_file(f), summary)
                    register_plugin_mock.assert_called_with('simpledsapp', '1.0.6', 'host')
                    register_plugin_by_url_mock.assert_called_with('http://127.0.0.1:8010/api/v1/1/',
                                                              'host')

            with mock.patch.object(pl_admin.PluginManager, 'register_plugin_by_url',
                                   side_effect=Exception('Error')):
                summary = {'success': [{'plugin_name': 'simplefsapp'},
                                       {'plugin_name': 'simpledsapp'}
                                       ],
                           'error': [{'plugin_name': 'http://127.0.0.1:8010/api/v1/1/',
                                      'code': 'Error'}]}
                with io.BytesIO(file_content) as f:
                    self.assertEqual(plugin_admin.register_plugins_from_file(f), summary)
