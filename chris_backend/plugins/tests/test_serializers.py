
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User

from rest_framework import serializers

from plugins.models import Plugin, PluginParameter, PluginInstance, ComputeResource
from plugins.serializers import PluginSerializer, PluginParameterSerializer
from plugins.serializers import PluginInstanceSerializer


class SerializerTests(TestCase):

    def setUp(self):
        self.username = 'foo'
        self.password = 'foopassword'
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
        PluginParameter.objects.get_or_create(
            plugin=plugin,
            name=parameters[0]['name'],
            type=parameters[0]['type'],
            flag=parameters[0]['flag'])

        # create user
        User.objects.create_user(username=self.username, password=self.password)


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
            self.assertEquals(100, PluginSerializer.validate_app_cpu_descriptor('100m'))

    def test_validate_app_memory_descriptor(self):
        """
        Test whether custom validate_app_memory_descriptor method raises a ValidationError
        when the app memory descriptor cannot be converted to a fields.MemoryInt.
        """
        with self.assertRaises(serializers.ValidationError):
            PluginSerializer.validate_app_cpu_descriptor('100me')
            self.assertEquals(100, PluginSerializer.validate_app_cpu_descriptor('100mi'))
            self.assertEquals(100, PluginSerializer.validate_app_cpu_descriptor('100gi'))

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


class PluginInstanceSerializerTests(SerializerTests):

    def test_create(self):
        """
        Test whether custom validate_app_workers_descriptor method raises a ValidationError
        when the app worker descriptor cannot be converted to a positive integer.
        """
        pass
        # plugin = Plugin.objects.get(name=self.plugin_name)
        # user = User.objects.get(username=self.username)
        # data = {'plugin': plugin,
        #         'owner': user,
        #         'compute_resource': plugin.compute_resource}
        # plg_inst_serializer = PluginInstanceSerializer(data=data)
        # import pdb; pdb.set_trace()
        # plg_inst_serializer.is_valid(raise_exception=True)
        # plg_inst_serializer.context = {'view': mock.Mock()}
        # plg_inst_serializer.context['view'].get_object = mock.Mock(return_value=plugin)
        # plg_inst_serializer.create(plg_inst_serializer.validated_data)
        # self.assertEqual(plg_inst_serializer.validated_data['gpu_limit'],
        #                  plugin.min_gpu_limit)
