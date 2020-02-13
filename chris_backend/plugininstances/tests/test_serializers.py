
import logging
from unittest import mock

from django.test import TestCase
from django.contrib.auth.models import User

from rest_framework import serializers

from plugins.models import Plugin, PluginParameter, ComputeResource
from plugininstances.models import PluginInstance
from plugininstances.serializers import PluginInstanceSerializer
from plugininstances.serializers import (PathParameterSerializer,
                                         UnextpathParameterSerializer)


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


class PathParameterSerializerTests(SerializerTests):

    def setUp(self):
        super(PathParameterSerializerTests, self).setUp()
        self.plugin = Plugin.objects.get(name=self.plugin_name)
        self.user = User.objects.get(username=self.username)
        self.other_username = 'boo'
        self.other_password = 'far'

    def test_validate_value_fail_denied_acces_other_user_space(self):
        """
        Test whether overriden validate_value method raises a serializers.ValidationError
        when user tries to access another user's space.
        """
        path_parm_serializer = PathParameterSerializer(user=self.user)
        with self.assertRaises(serializers.ValidationError):
            value = "{}/uploads, anotheruser".format(self.username)
            path_parm_serializer.validate_value(value)
        with self.assertRaises(serializers.ValidationError):
            value = "{}, anotheruser/uploads".format(self.username, self.username)
            path_parm_serializer.validate_value(value)

    def test_validate_value_fail_invalid_feed_path(self):
        """
        Test whether overriden validate_value method raises a serializers.ValidationError
        when user tries to access another user's invalid feed path.
        """
        user = User.objects.get(username=self.username)
        user1 = User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        plugin = self.plugin
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user1,
                                                compute_resource=plugin.compute_resource)
        path_parm_serializer = PathParameterSerializer(user=user)
        # but feed id
        with self.assertRaises(serializers.ValidationError):
            path_parm_serializer.validate_value(self.other_username + '/feed_butnumber')
        # feed id does not exist in the DB
        with self.assertRaises(serializers.ValidationError):
            path_parm_serializer.validate_value(self.other_username + '/feed_%s' %
                                                (pl_inst.feed.id + 1))
        # user is not owner of this existing feed
        with self.assertRaises(serializers.ValidationError):
            path_parm_serializer.validate_value(self.other_username + '/feed_%s' %
                                                pl_inst.feed.id)

    def test_validate_value_success(self):
        """
        Test whether overriden validate_value method successfully returns a valid
        string of paths separated by comma.
        """
        user = User.objects.get(username=self.username)
        user1 = User.objects.create_user(username=self.other_username,
                                         password=self.other_password)
        plugin = self.plugin
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user1,
                                                compute_resource=plugin.compute_resource)
        pl_inst.feed.owner.set([user1, user])
        path_parm_serializer = PathParameterSerializer(user=user)
        value = "{}, {}/feed_{} ".format(self.username, self.other_username,
                                         pl_inst.feed.id)
        returned_value = path_parm_serializer.validate_value(value)
        self.assertEqual(returned_value, "{},{}/feed_{}".format(self.username,
                                                                self.other_username,
                                                                pl_inst.feed.id))


class UnextpathParameterSerializerTests(SerializerTests):

    def setUp(self):
        super(UnextpathParameterSerializerTests, self).setUp()
        self.plugin = Plugin.objects.get(name=self.plugin_name)
        self.user = User.objects.get(username=self.username)
        self.other_username = 'boo'
        self.other_password = 'far'

    def test_validate_value_fail_denied_acces_other_user_space(self):
        """
        Test whether overriden validate_value method raises a serializers.ValidationError
        when user tries to access another user's space.
        """
        path_parm_serializer = UnextpathParameterSerializer(user=self.user)
        with self.assertRaises(serializers.ValidationError):
            value = "{}/uploads, anotheruser".format(self.username)
            path_parm_serializer.validate_value(value)
        with self.assertRaises(serializers.ValidationError):
            value = "{}, anotheruser/uploads".format(self.username, self.username)
            path_parm_serializer.validate_value(value)

    def test_validate_value_fail_invalid_feed_path(self):
        """
        Test whether overriden validate_value method raises a serializers.ValidationError
        when user tries to access another user's invalid feed path.
        """
        user = User.objects.get(username=self.username)
        user1 = User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        plugin = self.plugin
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user1,
                                                compute_resource=plugin.compute_resource)
        path_parm_serializer = UnextpathParameterSerializer(user=user)
        # but feed id
        with self.assertRaises(serializers.ValidationError):
            path_parm_serializer.validate_value(self.other_username + '/feed_butnumber')
        # feed id does not exist in the DB
        with self.assertRaises(serializers.ValidationError):
            path_parm_serializer.validate_value(self.other_username + '/feed_%s' %
                                                (pl_inst.feed.id + 1))
        # user is not owner of this existing feed
        with self.assertRaises(serializers.ValidationError):
            path_parm_serializer.validate_value(self.other_username + '/feed_%s' %
                                                pl_inst.feed.id)

    def test_validate_value_success(self):
        """
        Test whether overriden validate_value method successfully returns a valid
        string of paths separated by comma.
        """
        user = User.objects.get(username=self.username)
        user1 = User.objects.create_user(username=self.other_username,
                                         password=self.other_password)
        plugin = self.plugin
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user1,
                                                compute_resource=plugin.compute_resource)
        pl_inst.feed.owner.set([user1, user])
        path_parm_serializer = UnextpathParameterSerializer(user=user)
        value = "{}, {}/feed_{} ".format(self.username, self.other_username,
                                         pl_inst.feed.id)
        returned_value = path_parm_serializer.validate_value(value)
        self.assertEqual(returned_value, "{},{}/feed_{}".format(self.username,
                                                                self.other_username,
                                                                pl_inst.feed.id))
