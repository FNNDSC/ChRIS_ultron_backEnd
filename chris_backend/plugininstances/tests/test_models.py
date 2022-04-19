
import logging
import os
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.conf import settings

from feeds.models import Feed
from plugins.models import PluginMeta, Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultStrParameter
from plugininstances.models import PluginInstance, PluginInstanceFile
from plugininstances.models import PluginInstanceFilter


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.plugin_fs_name = "simplecopyapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': True,
                                             'default': "./"}}
        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'prefix': {'type': 'string', 'optional': False}}
        self.username = 'foo'
        self.password = 'foo-pass'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL, compute_user='pfcon',
            compute_password='pfcon1234')

        # create plugins
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_fs_name,
                                                         type='fs')
        (plugin_fs, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_fs.compute_resources.set([self.compute_resource])
        plugin_fs.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ds_name,
                                                         type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

        # add plugins' parameters
        (plg_param, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])
        default = self.plugin_fs_parameters['dir']['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param, value=default)

        PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='prefix',
            type=self.plugin_ds_parameters['prefix']['type'],
            optional=self.plugin_ds_parameters['prefix']['optional'])

        # create user
        User.objects.create_user(username=self.username,
                                 password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class PluginInstanceModelTests(ModelTests):

    def test_save_creates_new_feed_just_after_fs_plugininstance_is_created(self):
        """
        Test whether overriden save method creates a feed just after an 'fs' plugin 
        instance is created.
        """
        # create an 'fs' plugin instance that in turn should create a new feed
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        self.assertEqual(Feed.objects.count(), 1)
        self.assertEqual(pl_inst.feed.name, pl_inst.plugin.meta.name)

    def test_save_does_not_create_new_feed_just_after_ds_plugininstance_is_created(self):
        """
        Test whether overriden save method does not create a feed just after a 'ds' plugin
        instance is created.
        """
        # create a 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        plg_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        # create a 'ds' plugin instance whose previous is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)
        PluginInstance.objects.create(plugin=plugin, owner=user, previous=plg_inst,
                                      compute_resource=plugin.compute_resources.all()[0])
        # the new 'ds' plugin instance shouldn't create a new feed
        self.assertEqual(Feed.objects.count(), 1)

    def test_get_root_instance(self):
        """
        Test whether custom get_root_instance method returns the root 'fs' plugin 
        instance for a give plugin instance.
        """
        # create a 'fs' plugin instance 
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        plg_inst_root = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        # create a 'ds' plugin instance whose root is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)
        plg_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, previous=plg_inst_root,
            compute_resource=plugin.compute_resources.all()[0])
        root_instance = plg_inst.get_root_instance()
        self.assertEqual(root_instance, plg_inst_root)

    def test_get_descendant_instances(self):
        """
        Test whether custom get_descendant_instances method returns all the plugin
        instances that are a descendant of a plugin instance
        """
        # create a 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        plg_inst_root = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        # create a 'ds' plugin instance whose previous is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)
        plg_inst1 = PluginInstance.objects.create(
            plugin=plugin, owner=user, previous=plg_inst_root,
            compute_resource=plugin.compute_resources.all()[0])
        # create another 'ds' plugin instance whose previous is the previous 'ds' plugin
        # instance
        plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)
        plg_inst2 = PluginInstance.objects.create(
            plugin=plugin, owner=user, previous=plg_inst1,
            compute_resource=plugin.compute_resources.all()[0])
        decend_instances = plg_inst_root.get_descendant_instances()
        self.assertEqual(len(decend_instances), 3)
        self.assertEqual(decend_instances[0], plg_inst_root)
        self.assertEqual(decend_instances[1], plg_inst1)
        self.assertEqual(decend_instances[2], plg_inst2)

    def test_get_output_path(self):
        """
        Test whether custom get_output_path method returns appropriate output paths
        for both 'fs' and 'ds' plugins.
        """
        # create an 'fs' plugin instance 
        user = User.objects.get(username=self.username)
        plugin_fs = Plugin.objects.get(meta__name=self.plugin_fs_name)
        pl_inst_fs = PluginInstance.objects.create(
            plugin=plugin_fs,
            owner=user,
            compute_resource=plugin_fs.compute_resources.all()[0])
        # 'fs' plugins will output files to:
        # SWIFT_CONTAINER_NAME/<username>/feed_<id>/plugin_name_plugin_inst_<id>/data
        fs_output_path = '{0}/feed_{1}/{2}_{3}/data'.format( self.username,
                                                             pl_inst_fs.feed.id,
                                                             pl_inst_fs.plugin.meta.name,
                                                             pl_inst_fs.id) 
        self.assertEqual(pl_inst_fs.get_output_path(), fs_output_path)

        # create a 'ds' plugin instance 
        user = User.objects.get(username=self.username)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        pl_inst_ds = PluginInstance.objects.create(
            plugin=plugin_ds, owner=user, previous=pl_inst_fs,
            compute_resource=plugin_ds.compute_resources.all()[0])
        # 'ds' plugins will output files to:
        # SWIFT_CONTAINER_NAME/<username>/feed_<id>/...
        #/previous_plugin_name_plugin_inst_<id>/plugin_name_plugin_inst_<id>/data
        ds_output_path = os.path.join(os.path.dirname(fs_output_path),
                                      '{0}_{1}/data'.format(pl_inst_ds.plugin.meta.name,
                                                            pl_inst_ds.id))
        self.assertEqual(pl_inst_ds.get_output_path(), ds_output_path)


class PluginInstanceFilterModelTests(ModelTests):

    def test_filter_by_root_id(self):
        """
        Test whether custom filter_by_root_id method returns the plugin instances in a
        queryset with a common root plugin instance.
        """
        # create a 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        plg_inst_root = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        # create a 'ds' plugin instance whose previous is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)
        plg_inst1 = PluginInstance.objects.create(
            plugin=plugin, owner=user, previous=plg_inst_root,
            compute_resource=plugin.compute_resources.all()[0])
        # create another 'ds' plugin instance whose previous is the previous 'ds' plugin
        # instance
        plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)
        plg_inst2 = PluginInstance.objects.create(
            plugin=plugin, owner=user, previous=plg_inst1,
            compute_resource=plugin.compute_resources.all()[0])
        queryset = PluginInstance.objects.all()
        value = plg_inst1.id
        filter = PluginInstanceFilter()
        filtered_queryset = filter.filter_by_root_id(queryset, "", value)
        self.assertEqual(len(filtered_queryset), 2)
        self.assertIn(filtered_queryset[0], [plg_inst1, plg_inst2])
        self.assertIn(filtered_queryset[1], [plg_inst1, plg_inst2])
