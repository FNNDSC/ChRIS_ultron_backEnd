
import logging
from unittest import mock

from django.test import TestCase
from django.conf import settings
from rest_framework import serializers

from plugins.models import (ComputeResource, PluginMeta, Plugin, PluginParameter,
                            DefaultStrParameter)
from plugins.serializers import (PluginMetaSerializer, PluginSerializer,
                                 PluginParameterSerializer)


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class SerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.plugin_name = "simplecopyapp"
        plugin_parameters = [{'name': 'dir', 'type': 'string', 'action': 'store',
                              'optional': True, 'flag': '--dir', 'short_flag': '-d',
                              'default': '/', 'help': 'test plugin', 'ui_exposed': True}]

        self.plg_data = {'description': 'A simple chris fs app demo',
                         'version': '0.1',
                         'dock_image': 'fnndsc/pl-simplefsapp',
                         'execshell': 'python3',
                         'selfpath': '/usr/local/bin',
                         'selfexec': 'simplefsapp'}

        self.plg_meta_data = {'name': self.plugin_name,
                              'title': 'Dir plugin',
                              'license': 'MIT',
                              'type': 'fs',
                              'icon': 'http://github.com/plugin',
                              'category': 'Dir',
                              'stars': 0,
                              'authors': 'FNNDSC (dev@babyMRI.org)'}

        self.plugin_repr = self.plg_data.copy()
        self.plugin_repr.update(self.plg_meta_data)
        self.plugin_repr['parameters'] = plugin_parameters

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create a plugin
        data = self.plg_meta_data.copy()
        (pl_meta, tf) = PluginMeta.objects.get_or_create(**data)
        data = self.plg_data.copy()
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, **data)
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()

        # add plugin's parameters
        parameters = plugin_parameters
        (plg_param, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'],
            optional=parameters[0]['optional']
        )
        default = parameters[0]['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param, value=default)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class PluginMetaSerializerTests(SerializerTests):

    def test_update(self):
        """
        Test whether overriden update method changes modification date.
        """
        meta = PluginMeta.objects.get(name=self.plugin_name)
        initial_mod_date = meta.modification_date
        data = {'name': self.plugin_name, 'public_repo': 'http://github.com/plugin'}
        plg_meta_serializer = PluginMetaSerializer(meta, data)
        plg_meta_serializer.is_valid(raise_exception=True)
        meta = plg_meta_serializer.update(meta, plg_meta_serializer.validated_data)
        self.assertGreater(meta.modification_date, initial_mod_date)


class PluginSerializerTests(SerializerTests):

    def test_validate_version(self):
        """
        Test whether overriden validate_version method raises a ValidationError when
        wrong version type or format has been submitted.
        """
        plg_serializer = PluginSerializer()
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_version(1.2)
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate_version('v1.2')

    def test_validate_app_workers_descriptor(self):
        """
        Test whether custom validate_app_workers_descriptor method raises a ValidationError
        when the app worker descriptor cannot be converted to a positive integer.
        """
        with self.assertRaises(serializers.ValidationError):
            descriptor_dict = {'name': 'min_number_of_workers', 'value': 'one'}
            PluginSerializer.validate_app_workers_descriptor(descriptor_dict)
        with self.assertRaises(serializers.ValidationError):
            descriptor_dict = {'name': 'max_number_of_workers', 'value': 0}
            PluginSerializer.validate_app_workers_descriptor(descriptor_dict)

    def test_validate_app_cpu_descriptor(self):
        """
        Test whether custom validate_app_cpu_descriptor method raises a ValidationError
        when the app cpu descriptor cannot be converted to a fields.CPUInt.
        """
        with self.assertRaises(serializers.ValidationError):
            descriptor_dict = {'name': 'min_cpu_limit', 'value': '100me'}
            PluginSerializer.validate_app_cpu_descriptor(descriptor_dict)
            descriptor_dict = {'name': 'max_cpu_limit', 'value': '100m'}
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor(descriptor_dict))

    def test_validate_app_memory_descriptor(self):
        """
        Test whether custom validate_app_memory_descriptor method raises a ValidationError
        when the app memory descriptor cannot be converted to a fields.MemoryInt.
        """
        with self.assertRaises(serializers.ValidationError):
            descriptor_dict = {'name': 'min_memory_limit', 'value': '100me'}
            PluginSerializer.validate_app_cpu_descriptor(descriptor_dict)
            descriptor_dict = {'name': 'min_memory_limit', 'value': '100mi'}
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor(descriptor_dict))
            descriptor_dict = {'name': 'max_memory_limit', 'value': '100gi'}
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor(descriptor_dict))

    def test_validate_app_gpu_descriptor(self):
        """
        Test whether custom validate_app_gpu_descriptor method raises a ValidationError
        when the gpu descriptor cannot be converted to a non-negative integer.
        """
        with self.assertRaises(serializers.ValidationError):
            descriptor_dict = {'name': 'min_gpu_limit', 'value': 'one'}
            PluginSerializer.validate_app_gpu_descriptor(descriptor_dict)
        with self.assertRaises(serializers.ValidationError):
            descriptor_dict = {'name': 'max_gpu_limit', 'value': -1}
            PluginSerializer.validate_app_gpu_descriptor(descriptor_dict)

    def test_validate_app_int_descriptor(self):
        """
        Test whether custom validate_app_int_descriptor method raises a ValidationError
        when the descriptor cannot be converted to a non-negative integer.
        """
        error_msg = "This field must be a non-negative integer."
        with self.assertRaises(serializers.ValidationError):
            descriptor_dict = {'name': 'field_name', 'value': 'one'}
            PluginSerializer.validate_app_int_descriptor(descriptor_dict, error_msg)
        with self.assertRaises(serializers.ValidationError):
            descriptor_dict = {'name': 'field_name', 'value': -1}
            PluginSerializer.validate_app_int_descriptor(descriptor_dict, error_msg)

    def test_validate_app_descriptor_limits(self):
        """
        Test whether custom validate_app_descriptor_limit method raises a ValidationError
        when the max limit is smaller than the min limit.
        """
        self.plugin_repr['min_cpu_limit'] = 200
        self.plugin_repr['max_cpu_limit'] = 100
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_descriptor_limits(self.plugin_repr,
                                                            'min_cpu_limit',
                                                            'max_cpu_limit')

    def test_validate_workers_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_number_of_workers' is smaller than the 'min_number_of_workers'.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        self.plugin_repr['min_number_of_workers'] = 2
        self.plugin_repr['max_number_of_workers'] = 1
        data = self.plugin_repr.copy()
        del data['parameters']
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate(data)

    def test_validate_cpu_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_cpu_limit' is smaller than the 'min_cpu_limit'.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        self.plugin_repr['min_cpu_limit'] = 200
        self.plugin_repr['max_cpu_limit'] = 100
        data = self.plugin_repr.copy()
        del data['parameters']
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate(data)

    def test_validate_memory_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_memory_limit' is smaller than the 'min_memory_limit'.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        self.plugin_repr['min_memory_limit'] = 100000
        self.plugin_repr['max_memory_limit'] = 10000
        data = self.plugin_repr.copy()
        del data['parameters']
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate(data)

    def test_validate_gpu_limits(self):
        """
        Test whether custom validate method raises a ValidationError when the
        'max_gpu_limit' is smaller than the 'max_gpu_limit'.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        self.plugin_repr['min_gpu_limit'] = 2
        self.plugin_repr['max_gpu_limit'] = 1
        data = self.plugin_repr.copy()
        del data['parameters']
        with self.assertRaises(serializers.ValidationError):
            plg_serializer.validate(data)

    def test_validate_validates_min_number_of_workers(self):
        """
        Test whether custom validate method validates the 'min_number_of_workers'
        descriptor.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_number_of_workers'] = 4
        plg_serializer.validate_app_workers_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_workers_descriptor.assert_called_with(
            {'name': 'min_number_of_workers', 'value': 4})

    def test_validate_validates_max_number_of_workers(self):
        """
        Test whether custom validate method validates the 'max_number_of_workers'
        descriptor.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_number_of_workers'] = 5
        plg_serializer.validate_app_workers_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_workers_descriptor.assert_called_with(
            {'name': 'max_number_of_workers', 'value': 5})

    def test_validate_validates_min_gpu_limit(self):
        """
        Test whether custom validate method validates the 'min_gpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_gpu_limit'] = 1
        plg_serializer.validate_app_gpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_gpu_descriptor.assert_called_with(
            {'name': 'min_gpu_limit', 'value': 1})

    def test_validate_validates_max_gpu_limit(self):
        """
        Test whether custom validate method validates the 'max_gpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_gpu_limit'] = 2
        plg_serializer.validate_app_gpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_gpu_descriptor.assert_called_with(
            {'name': 'max_gpu_limit', 'value': 2})

    def test_validate_validates_min_cpu_limit(self):
        """
        Test whether custom validate method validates the 'min_cpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_cpu_limit'] = 100
        plg_serializer.validate_app_cpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_cpu_descriptor.assert_called_with(
            {'name': 'min_cpu_limit', 'value': 100})

    def test_validate_validates_max_cpu_limit(self):
        """
        Test whether custom validate method validates the 'max_cpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_cpu_limit'] = 200
        plg_serializer.validate_app_cpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_cpu_descriptor.assert_called_with(
            {'name': 'max_cpu_limit', 'value': 200})

    def test_validate_validates_min_memory_limit(self):
        """
        Test whether custom validate method validates the 'min_memory_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_memory_limit'] = 10000
        plg_serializer.validate_app_memory_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_memory_descriptor.assert_called_with(
            {'name': 'min_memory_limit', 'value': 10000})

    def test_validate_validates_max_memory_limit(self):
        """
        Test whether custom validate method validates the 'max_memory_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(meta__name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_memory_limit'] = 100000
        plg_serializer.validate_app_memory_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_memory_descriptor.assert_called_with(
            {'name': 'max_memory_limit', 'value': 100000})


class PluginParameterSerializerTests(SerializerTests):

    def test_validate_validates_parameters_of_path_type_and_optional(self):
        """
        Test whether overriden validate method raises a ValidationError when
        a plugin parameter is optional anf of type 'path' or 'unextpath'.
        """
        with self.assertRaises(serializers.ValidationError):
            plg_param_serializer = PluginParameterSerializer()
            plg_param_serializer.validate({'optional': True, 'type': 'path'})
        with self.assertRaises(serializers.ValidationError):

            plg_param_serializer = PluginParameterSerializer()
            plg_param_serializer.validate({'optional': True, 'type': 'unextpath'})
