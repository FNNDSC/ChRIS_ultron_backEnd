
import logging
import os
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.contrib.auth.models import AnonymousUser, Group, User
from django.conf import settings

from core.models import ChrisFolder
from feeds.models import Feed
from plugins.models import PluginMeta, Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultStrParameter, DefaultIntParameter
from plugininstances.models import PluginInstance, PluginInstanceFilter
from plugininstances.models import StrParameter, IntParameter


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL
CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.plugin_fs_name = "simplecopyapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': True,
                                             'default': "./"}}
        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'prefix': {'type': 'string', 'optional': False},
                                     'dummyint': {'type': 'integer', 'optional': True,
                                                  'default': 0}}
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

        (plg_param, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyint',
            type=self.plugin_ds_parameters['dummyint']['type'],
            optional=self.plugin_ds_parameters['dummyint']['optional'])
        default = self.plugin_ds_parameters['dummyint']['default']
        DefaultIntParameter.objects.get_or_create(plugin_param=plg_param, value=default)

        # create user
        User.objects.create_user(username=self.username,
                                 password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def create_instance_tree(self):
        """
        Custom method to create a root 'fs' plugin instance with two 'ds' children, the
        first of which has a 'ds' child, and return the four instances.
        """
        user = User.objects.get(username=self.username)
        plugin_fs = Plugin.objects.get(meta__name=self.plugin_fs_name)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        root = PluginInstance.objects.create(plugin=plugin_fs, owner=user,
                                             compute_resource=self.compute_resource)
        (child1, child2) = [PluginInstance.objects.create(
            plugin=plugin_ds, owner=user, previous=root,
            compute_resource=self.compute_resource) for _ in range(2)]
        grandchild = PluginInstance.objects.create(plugin=plugin_ds, owner=user,
                                                   previous=child1,
                                                   compute_resource=self.compute_resource)
        return root, child1, child2, grandchild


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

    def test_save_creates_new_folders_just_after_plugininstance_is_created(self):
        """
        Test whether overriden save method creates new folders (output folder and
        possibly some of its ancestors) just after a plugin instance is created.
        """
        # create a plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        nfolders = len(ChrisFolder.objects.all())
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        folders = list(ChrisFolder.objects.all())
        self.assertTrue(len(folders)>nfolders)
        self.assertIn(pl_inst.output_folder, folders)

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
        plg_inst2 = PluginInstance.objects.create(
            plugin=plugin, owner=user, previous=plg_inst1,
            compute_resource=plugin.compute_resources.all()[0])
        decend_instances = plg_inst_root.get_descendant_instances()
        self.assertEqual(len(decend_instances), 3)
        self.assertEqual(decend_instances[0], plg_inst_root)
        self.assertEqual(decend_instances[1], plg_inst1)
        self.assertEqual(decend_instances[2], plg_inst2)

    def test_get_descendant_instances_runs_one_plain_query_per_instance(self):
        """
        Test whether custom get_descendant_instances method runs one query per visited
        plugin instance that fetches no related objects, so walking a big tree stays
        cheap for the callers that only need the instances' ids or status.
        """
        (root, child1, child2, grandchild) = self.create_instance_tree()
        with CaptureQueriesContext(connection) as walk:
            descendants = root.get_descendant_instances()
        self.assertCountEqual(descendants, [root, child1, child2, grandchild])
        self.assertEqual(len(walk), len(descendants))
        for query in walk.captured_queries:
            self.assertNotIn('JOIN', query['sql'])

    def test_get_parameter_instances(self):
        """
        Test whether custom get_parameter_instances method returns all the parameter
        instances associated with a plugin instance regardless of their type
        """
        # create a 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        plg_inst_root = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])

        # create a 'ds' plugin instance whose previous is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(meta__name=self.plugin_ds_name)
        str_plg_param = PluginParameter.objects.get(plugin=plugin, name='prefix')
        int_plg_param = PluginParameter.objects.get(plugin=plugin, name='dummyint')

        plg_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, previous=plg_inst_root,
            compute_resource=plugin.compute_resources.all()[0])

        StrParameter.objects.create(plugin_inst=plg_inst, plugin_param=str_plg_param,
                                    value='lo')
        IntParameter.objects.create(plugin_inst=plg_inst, plugin_param=int_plg_param,
                                    value=1)

        param_instances = plg_inst.get_parameter_instances()
        self.assertEqual(len(param_instances), 2)

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
        fs_output_path = (f'home/{self.username}/feeds/feed_'
                          f'{pl_inst_fs.feed.id}/{pl_inst_fs.plugin.meta.name}_{ pl_inst_fs.id}/data')
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

    def test_auto_delete_output_folder_with_plugin_instance(self):
        """
        Test whether deleting a plugin instance will automatically delete its output
        folder.
        """
        # create a plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(
            plugin=plugin,
            owner=user,
            compute_resource=plugin.compute_resources.all()[0])

        output_folder_path = pl_inst.output_folder.path
        folders = list(ChrisFolder.objects.all())
        self.assertIn(pl_inst.output_folder, folders)

        pl_inst.delete()

        with self.assertRaises(Exception):
            ChrisFolder.objects.get(path=output_folder_path)


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

    def test_filter_by_root_id_narrows_the_given_queryset(self):
        """
        Test whether custom filter_by_root_id method only returns plugin instances of
        the queryset it is given, so that the filters applied before it are kept.
        """
        (root, child1, child2, grandchild) = self.create_instance_tree()
        queryset = PluginInstance.objects.exclude(pk=grandchild.id)
        filtered_queryset = PluginInstanceFilter().filter_by_root_id(queryset, "",
                                                                     root.id)
        self.assertCountEqual(filtered_queryset, [root, child1, child2])

    def test_filter_by_previous_id_narrows_the_given_queryset(self):
        """
        Test whether custom filter_by_previous_id method only returns plugin instances
        of the queryset it is given, so that the filters applied before it are kept.
        """
        (root, child1, child2, grandchild) = self.create_instance_tree()
        queryset = PluginInstance.objects.exclude(pk=child2.id)
        filtered_queryset = PluginInstanceFilter().filter_by_previous_id(queryset, "",
                                                                         root.id)
        self.assertCountEqual(filtered_queryset, [child1])


class PluginInstanceVisibilityModelTests(ModelTests):
    """
    Test the custom filter_visible_to_user static method.
    """

    def setUp(self):
        super(PluginInstanceVisibilityModelTests, self).setUp()
        self.other_user = User.objects.create_user(username='boo', password=self.password)
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)

        # create two 'fs' plugin instances, one in a private and one in a public feed
        (self.private_inst, self.public_inst) = [PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=self.compute_resource)
            for _ in range(2)]
        self.public_inst.feed.public = True
        self.public_inst.feed.save()

    def visible_to(self, user):
        return PluginInstance.filter_visible_to_user(PluginInstance.objects.all(), user)

    def test_filter_visible_to_user_unauthenticated_sees_public_feeds_only(self):
        self.assertCountEqual(self.visible_to(AnonymousUser()), [self.public_inst])

    def test_filter_visible_to_user_chris_sees_every_feed(self):
        chris = User.objects.get(username=self.chris_username)
        self.assertCountEqual(self.visible_to(chris), [self.private_inst,
                                                       self.public_inst])

    def test_filter_visible_to_user_owner_sees_own_feeds(self):
        owner = User.objects.get(username=self.username)
        self.assertCountEqual(self.visible_to(owner), [self.private_inst,
                                                       self.public_inst])

    def test_filter_visible_to_user_other_user_sees_public_feeds_only(self):
        self.assertCountEqual(self.visible_to(self.other_user), [self.public_inst])

    def test_filter_visible_to_user_sees_feeds_shared_with_the_user(self):
        self.private_inst.feed.grant_user_permission(self.other_user)
        self.assertCountEqual(self.visible_to(self.other_user), [self.private_inst,
                                                                 self.public_inst])

    def test_filter_visible_to_user_sees_feeds_shared_with_a_group_of_the_user(self):
        group = Group.objects.create(name='lab')
        self.other_user.groups.add(group)
        self.private_inst.feed.grant_group_permission(group)
        self.assertCountEqual(self.visible_to(self.other_user), [self.private_inst,
                                                                 self.public_inst])

    def test_filter_visible_to_user_lists_once_an_instance_shared_many_times(self):
        group = Group.objects.create(name='lab')
        self.other_user.groups.add(group)
        third_user = User.objects.create_user(username='third', password=self.password)
        feed = self.private_inst.feed
        feed.grant_user_permission(self.other_user)
        feed.grant_user_permission(third_user)
        feed.grant_group_permission(group)

        for user in (User.objects.get(username=self.username), self.other_user):
            with self.subTest(user=user.username):
                self.assertCountEqual(self.visible_to(user), [self.private_inst,
                                                              self.public_inst])
