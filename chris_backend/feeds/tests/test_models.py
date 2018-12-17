
import logging

from django.test import TestCase
from django.contrib.auth.models import User

from plugins.models import Plugin, PluginParameter, PluginInstance, ComputeResource
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
            compute_resource_identifier="host")

        # create a "fs" plugin
        (plugin, tf) = Plugin.objects.get_or_create(name=self.plugin_name,
                                                    type=self.plugin_type,
                                                    compute_resource=self.compute_resource)
        # add plugin parameter
        PluginParameter.objects.get_or_create(
            plugin=plugin,
            name='mrn',
            type=self.plugin_parameters['mrn']['type'],
            optional=self.plugin_parameters['mrn']['optional'])

        # create user
        user = User.objects.create_user(username=self.username,
                                        password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)

    def test_save_creates_new_note_just_after_feed_is_created(self):
        """
        Test whether overriden save method creates a note just after a feed is created
        """
        # create a plugin instance that in turn creates a new feed
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user, 
                                            compute_resource=plugin.compute_resource)
        pl_inst.feed.name = self.feed_name
        self.assertEqual(Note.objects.count(), 1)
