
import logging
from unittest import mock

from django.test import TestCase
from django import forms
from django.utils import timezone

from plugins import admin as pl_admin


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
                                                    compute_resource_identifier="host")
        # create a plugin
        self.plugin_name = "simplecopyapp"
        self.plugin_version = "0.1"
        self.plugin = pl_admin.Plugin()
        self.plugin.name = self.plugin_name
        self.plugin.version = self.plugin_version
        self.plugin.compute_resource = self.compute_resource

    def test_clean_validate_name_version_and_save_plugin_descriptors(self):
        """
        Test whether overriden clean method validates the full set of plugin descriptors
        and save the newly created plugin to the DB.
        """
        # mock manager's add_plugin method
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(name=self.plugin_name,
                                                             version=self.plugin_version,
                                                compute_resource=self.compute_resource)

        with mock.patch.object(pl_admin.PluginManager, 'add_plugin',
                               return_value=plugin) as add_plugin_mock:
            plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
            form = plugin_admin.form
            form.instance = self.plugin
            form.cleaned_data = {'name': self.plugin_name, 'version': self.plugin_version,
                                 'compute_resource': 'host'}
            self.assertIsNone(form.instance.pk)
            form.clean(form)
            self.assertEqual(form.instance, plugin)
            self.assertIsNotNone(form.instance.pk)
            add_plugin_mock.assert_called_with(self.plugin_name, self.plugin_version,
                                               'host')

    def test_clean_validate_url_and_save_plugin_descriptors(self):
        """
        Test whether overriden clean method validates the full set of plugin descriptors
        and save the newly created plugin to the DB.
        """
        # mock manager's add_plugin_by_url method
        (plugin, tf) = pl_admin.Plugin.objects.get_or_create(name=self.plugin_name,
                                                             version=self.plugin_version,
                                                compute_resource=self.compute_resource)
        plugin_store_url = "http://127.0.0.1:8010/api/v1/1/"
        with mock.patch.object(pl_admin.PluginManager, 'add_plugin_by_url',
                               return_value=plugin) as add_plugin_by_url_mock:
            plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
            form = plugin_admin.form
            form.instance = self.plugin
            form.cleaned_data = {'url': plugin_store_url,
                                 'compute_resource': 'host'}
            self.assertIsNone(form.instance.pk)
            form.clean(form)
            self.assertEqual(form.cleaned_data.get('name'), self.plugin_name)
            self.assertEqual(form.cleaned_data.get('version'), self.plugin_version)
            self.assertNotIn('url', form.cleaned_data)
            self.assertEqual(form.instance, plugin)
            self.assertIsNotNone(form.instance.pk)
            add_plugin_by_url_mock.assert_called_with(plugin_store_url, 'host')

    def test_clean_raises_validation_error_if_cannot_add_plugin(self):
        """
        Test whether overriden clean method raises a ValidationError when there
        is a validation error or it cannot save a new plugin to the DB.
        """
        # mock manager's add_plugin method
        with mock.patch.object(pl_admin.PluginManager, 'add_plugin',
                               side_effect=Exception) as add_plugin_mock:
            plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
            form = plugin_admin.form
            form.instance = self.plugin
            form.cleaned_data = {'name': self.plugin_name, 'version': self.plugin_version,
                                 'compute_resource': 'host'}
            self.assertIsNone(form.instance.pk)
            with self.assertRaises(forms.ValidationError):
                form.clean(form)


class PluginAdminTests(TestCase):
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

    def test_add_view(self):
        """
        Test whether overriden add_view method only shows the required fields in the add
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
        Test whether overriden change_view method shows all plugin fields in readonly
        mode except the 'compute_resource' field that is shown in editable mode.
        """
        plugin_admin = pl_admin.PluginAdmin(pl_admin.Plugin, pl_admin.admin.site)
        request_mock = mock.Mock()
        with mock.patch.object(pl_admin.admin.ModelAdmin, 'change_view',
                               return_value=None) as change_view_mock:
            plugin_admin.change_view(request_mock, 1)
            self.assertNotIn('compute_resource', plugin_admin.readonly_fields)
            self.assertEqual(len(plugin_admin.fieldsets), 2)
            self.assertEqual(len(plugin_admin.readonly_fields),
                             len(plugin_admin.fieldsets[1][1]['fields']))
            change_view_mock.assert_called_with(plugin_admin, request_mock, 1, '', None)

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
            save_model_mock.assert_called_with(request_mock, form_mock.instance,
                                               form_mock, False)

            plugin_admin.save_model(request_mock, obj_mock, form_mock, True)
            save_model_mock.assert_called_with(request_mock, obj_mock, form_mock, True)
            self.assertGreater(obj_mock.modification_date, obj_mock_creation_date)
