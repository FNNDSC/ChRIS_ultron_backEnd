
import logging

from django.test import TestCase
from django.contrib.auth.models import User

from plugins.models import PluginMeta, Plugin, PluginParameter, ComputeResource
from plugininstances.models import PluginInstance
from feeds.models import Note, Feed


class FeedModelTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.feed_name = "Feed1"
        self.plugin_name = "pacspull"
        self.plugin_type = "fs"
        self.plugin_parameters = {'mrn': {'type': 'string', 'optional': False},
                                  'img_type': {'type': 'string', 'optional': True}}
        self.username = 'foo'
        self.password = 'bar'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", description="host description")

        # create a "fs" plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                         type=self.plugin_type)
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()

        # add plugin parameter
        PluginParameter.objects.get_or_create(
            plugin=plugin,
            name='mrn',
            type=self.plugin_parameters['mrn']['type'],
            optional=self.plugin_parameters['mrn']['optional'])

        # create user
        user = User.objects.create_user(username=self.username,
                                        password=self.password)

        # create a plugin instance that in turn creates a new feed
        (plg_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        plg_inst.feed.name = self.feed_name
        plg_inst.feed.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)

    def test_save_creates_new_note_just_after_feed_is_created(self):
        """
        Test whether overriden save method creates a note just after a feed is created.
        """
        self.assertEqual(Note.objects.count(), 1)

    def test_get_creator(self):
        """
        Test whether custom get_creator method properly returns the user that created the
        feed.
        """
        user = User.objects.get(username=self.username)
        feed = Feed.objects.get(name=self.feed_name)
        feed_creator = feed.get_creator()
        self.assertEqual(feed_creator, user)

    def test_get_plugin_instances_status_count(self):
        """
        Test whether custom get_plugin_instances_status_count method properly returns
        the number of plugin instances with a specific exec status.
        """
        feed = Feed.objects.get(name=self.feed_name)
        count = feed.get_plugin_instances_status_count('started')
        self.assertEqual(count, 1)
        count = feed.get_plugin_instances_status_count('finishedSuccessfully')
        self.assertEqual(count, 0)
        count = feed.get_plugin_instances_status_count('finishedWithError')
        self.assertEqual(count, 0)
        count = feed.get_plugin_instances_status_count('cancelled')
        self.assertEqual(count, 0)
