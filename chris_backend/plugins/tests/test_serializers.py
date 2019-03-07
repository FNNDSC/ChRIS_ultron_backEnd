
import logging
from unittest import mock

from django.test import TestCase
from rest_framework import serializers

from plugins.models import Plugin
from plugins.models import PluginParameter, DefaultPathParameter
from plugins.models import ComputeResource
from plugins.serializers import PluginSerializer


class SerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.plugin_name = "simplefsapp"
        self.plugin_repr = {"name": "simplefsapp", "dock_image": "fnndsc/pl-simplefsapp",
                            "authors": "FNNDSC (dev@babyMRI.org)", "type": "fs",
                            "description": "A simple chris fs app demo", "version": "0.1",
                            "title": "Simple chris fs app", "license": "Opensource (MIT)",

                            "parameters": [{"optional": True, "action": "store",
                                            "help": "look up directory", "type": "path",
                                            "name": "dir", "flag": "--dir",
                                            "default": "./"}],

                            "selfpath": "/usr/src/simplefsapp",
                            "selfexec": "simplefsapp.py", "execshell": "python3"}

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create a plugin
        data = self.plugin_repr.copy()
        parameters = self.plugin_repr['parameters']
        del data['parameters']
        data['compute_resource'] = self.compute_resource
        (plugin, tf) = Plugin.objects.get_or_create(**data)

        # add plugin's parameters
        (plg_param, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'],
            optional=parameters[0]['optional']
        )
        default = parameters[0]['default']
        DefaultPathParameter.objects.get_or_create(plugin_param=plg_param, value=default)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PluginSerializerTests(SerializerTests):

    def test_validate_app_workers_descriptor(self):
        """
        Test whether custom validate_app_workers_descriptor method raises a ValidationError
        when the app worker descriptor cannot be converted to a positive integer.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_workers_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_workers_descriptor(0)

    def test_validate_app_cpu_descriptor(self):
        """
        Test whether custom validate_app_cpu_descriptor method raises a ValidationError
        when the app cpu descriptor cannot be converted to a fields.CPUInt.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_cpu_descriptor('100me')
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor('100m'))

    def test_validate_app_memory_descriptor(self):
        """
        Test whether custom validate_app_memory_descriptor method raises a ValidationError
        when the app memory descriptor cannot be converted to a fields.MemoryInt.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_cpu_descriptor('100me')
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor('100mi'))
            self.assertEqual(100, PluginSerializer.validate_app_cpu_descriptor('100gi'))

    def test_validate_app_gpu_descriptor(self):
        """
        Test whether custom validate_app_gpu_descriptor method raises a ValidationError
        when the gpu descriptor cannot be converted to a non-negative integer.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_gpu_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_gpu_descriptor(-1)

    def test_validate_app_int_descriptor(self):
        """
        Test whether custom validate_app_int_descriptor method raises a ValidationError
        when the descriptor cannot be converted to a non-negative integer.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_int_descriptor('one')
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_int_descriptor(-1)

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
        plugin = Plugin.objects.get(name=self.plugin_name)
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
        plugin = Plugin.objects.get(name=self.plugin_name)
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
        plugin = Plugin.objects.get(name=self.plugin_name)
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
        plugin = Plugin.objects.get(name=self.plugin_name)
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
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_number_of_workers'] = 4
        plg_serializer.validate_app_workers_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_workers_descriptor.assert_called_with(4)

    def test_validate_validates_max_number_of_workers(self):
        """
        Test whether custom validate method validates the 'max_number_of_workers'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_number_of_workers'] = 5
        plg_serializer.validate_app_workers_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_workers_descriptor.assert_called_with(5)

    def test_validate_validates_min_gpu_limit(self):
        """
        Test whether custom validate method validates the 'min_gpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_gpu_limit'] = 1
        plg_serializer.validate_app_gpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_gpu_descriptor.assert_called_with(1)

    def test_validate_validates_max_gpu_limit(self):
        """
        Test whether custom validate method validates the 'max_gpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_gpu_limit'] = 2
        plg_serializer.validate_app_gpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_gpu_descriptor.assert_called_with(2)

    def test_validate_validates_min_cpu_limit(self):
        """
        Test whether custom validate method validates the 'min_cpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_cpu_limit'] = 100
        plg_serializer.validate_app_cpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_cpu_descriptor.assert_called_with(100)

    def test_validate_validates_max_cpu_limit(self):
        """
        Test whether custom validate method validates the 'max_cpu_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_cpu_limit'] = 200
        plg_serializer.validate_app_cpu_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_cpu_descriptor.assert_called_with(200)

    def test_validate_validates_min_memory_limit(self):
        """
        Test whether custom validate method validates the 'min_memory_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['min_memory_limit'] = 10000
        plg_serializer.validate_app_memory_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_memory_descriptor.assert_called_with(10000)

    def test_validate_validates_max_memory_limit(self):
        """
        Test whether custom validate method validates the 'max_memory_limit'
        descriptor.
        """
        plugin = Plugin.objects.get(name=self.plugin_name)
        plg_serializer = PluginSerializer(plugin)
        data = self.plugin_repr.copy()
        del data['parameters']
        data['max_memory_limit'] = 100000
        plg_serializer.validate_app_memory_descriptor = mock.Mock()
        plg_serializer.validate(data)
        plg_serializer.validate_app_memory_descriptor.assert_called_with(100000)
