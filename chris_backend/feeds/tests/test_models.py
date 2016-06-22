
from django.test import TestCase

from plugins.models import Plugin
from feeds.models import Note, Feed


class FeedModelTests(TestCase):
    
    def setUp(self):
        self.feed_name = "Feed1"
        self.plugin_name = "pacspull"
        self.plugin_type = "fs"

        # create a "fs" plugin
        (plugin, tf) = Plugin.objects.get_or_create(name=self.plugin_name,
                                                    type=self.plugin_type)
        # create a feed
        Feed.objects.create(name=self.feed_name, plugin=plugin)

    def test_save_creates_new_note_just_after_feed_is_created(self):
        """
        Test whether overriden save method creates a note just after a feed is created
        """
        self.assertEquals(Note.objects.count(), 1)
