
import logging
from unittest import mock

from django.test import TestCase
from django.contrib.auth.models import User

from rest_framework import serializers

from plugins.models import Plugin, PluginParameter, ComputeResource
from plugininstances.models import PluginInstance
from plugininstances.serializers import PluginInstanceSerializer


class SerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

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

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PluginInstanceSerializerTests(SerializerTests):

    def setUp(self):
        super(PluginInstanceSerializerTests, self).setUp()
        self.plugin = Plugin.objects.get(name=self.plugin_name)
        self.user = User.objects.get(username=self.username)
        self.data = {'plugin': self.plugin,
                     'owner': self.user,
                     'compute_resource': self.plugin.compute_resource}

    def test_validate_previous(self):
        """
        Test whether custom validate_previous method returns a previous instance or
        raises a serializers.ValidationError.
        """
        plugin = self.plugin
        # create an 'fs' plugin instance
        pl_inst_fs = PluginInstance.objects.create(plugin=plugin, owner=self.user,
                                                   compute_resource=plugin.compute_resource)
        # create a 'ds' plugin
        data = self.plugin_repr.copy()
        del data['parameters']
        data['name'] = 'testdsapp'
        data['type'] = 'ds'
        data['compute_resource'] = self.compute_resource
        (plugin, tf) = Plugin.objects.get_or_create(**data)
        data = {'plugin': plugin,
                'owner': self.user,
                'compute_resource': plugin.compute_resource}

        # create serializer for a 'ds' plugin instance
        plg_inst_serializer = PluginInstanceSerializer(data=data)
        plg_inst_serializer.is_valid(raise_exception=True)
        plg_inst_serializer.context['view'] = mock.Mock()
        plg_inst_serializer.context['view'].get_object = mock.Mock(return_value=plugin)
        plg_inst_serializer.context['request'] = mock.Mock()
        plg_inst_serializer.context['request'].user = self.user
        previous = plg_inst_serializer.validate_previous(pl_inst_fs.id)

        self.assertEqual(previous, pl_inst_fs)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_previous('')

    def test_validate_status(self):
        """
        Test whether overriden validate_status method raises a serializers.ValidationError
        when the status is not 'cancelled' or the current instance status is not 'started'
        or 'cancelled'.
        """
        plugin = self.plugin
        owner = self.user
        (plg_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=owner,
                                                compute_resource=plugin.compute_resource)
        plg_inst_serializer = PluginInstanceSerializer(plg_inst)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_status('finishedSuccessfully')

        (plg_inst, tf) = PluginInstance.objects.get_or_create(plugin=plugin, owner=owner,
                                                compute_resource=plugin.compute_resource)
        plg_inst.status = 'finishedSuccessfully'
        plg_inst_serializer = PluginInstanceSerializer(plg_inst)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_status('cancelled')

    def test_validate_gpu_limit(self):
        """
        Test whether custom validate_gpu_limit raises a serializers.ValidationError when
        the gpu_limit is not within the limits provided by the corresponding plugin.
        """
        data = self.data
        plugin = self.plugin
        plg_inst_serializer = PluginInstanceSerializer(data=data)
        plg_inst_serializer.is_valid(raise_exception=True)
        plg_inst_serializer.context['view'] = mock.Mock()
        plg_inst_serializer.context['view'].get_object = mock.Mock(return_value=plugin)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_gpu_limit(plugin.min_gpu_limit-1)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_gpu_limit(plugin.max_gpu_limit+1)

    def test_validate_number_of_workers(self):
        """
        Test whether custom validate_number_of_workers raises a serializers.ValidationError
        when the number_of_workers is not within the limits provided by the corresponding
        plugin.
        """
        data = self.data
        plugin = self.plugin
        plg_inst_serializer = PluginInstanceSerializer(data=data)
        plg_inst_serializer.is_valid(raise_exception=True)
        plg_inst_serializer.context['view'] = mock.Mock()
        plg_inst_serializer.context['view'].get_object = mock.Mock(return_value=plugin)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_number_of_workers(plugin.min_number_of_workers-1)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_number_of_workers(plugin.max_number_of_workers+1)

    def test_validate_cpu_limit(self):
        """
        Test whether custom validate_cpu_limit raises a serializers.ValidationError when
        the cpu_limit is not within the limits provided by the corresponding plugin.
        """
        data = self.data
        plugin = self.plugin
        plg_inst_serializer = PluginInstanceSerializer(data=data)
        plg_inst_serializer.is_valid(raise_exception=True)
        plg_inst_serializer.context['view'] = mock.Mock()
        plg_inst_serializer.context['view'].get_object = mock.Mock(return_value=plugin)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_cpu_limit(plugin.min_cpu_limit-1)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_cpu_limit(plugin.max_cpu_limit+1)

    def test_validate_memory_limit(self):
        """
        Test whether custom validate_memory_limit raises a serializers.ValidationError
        when the memory_limit is not within the limits provided by the corresponding
        plugin.
        """
        data = self.data
        plugin = self.plugin
        plg_inst_serializer = PluginInstanceSerializer(data=data)
        plg_inst_serializer.is_valid(raise_exception=True)
        plg_inst_serializer.context['view'] = mock.Mock()
        plg_inst_serializer.context['view'].get_object = mock.Mock(return_value=plugin)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_memory_limit(plugin.min_memory_limit-1)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_memory_limit(plugin.max_memory_limit+1)

    def test_validate_value_within_interval(self):
        """
        Test whether custom validate_value_within_interval raises a
        serializers.ValidationError when the first argument is not within the interval
        provided by the second and third argument.
        """
        plugin = self.plugin
        plg_inst_serializer = PluginInstanceSerializer(plugin)
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_value_within_interval(1, 2, 4, 'error: below')
        with self.assertRaises(serializers.ValidationError):
            plg_inst_serializer.validate_value_within_interval(5, 2, 4, 'error: above')
