
import logging
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User

from rest_framework import serializers

from plugins.models import PluginMeta, Plugin, ComputeResource
from plugininstances.models import PluginInstance
from feeds.models import Feed, Tag, Tagging
from feeds.serializers import TaggingSerializer, FeedSerializer


class SerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.username = 'foo'
        self.password = 'bar'
        self.feedname = "Feed1"
        self.other_username = 'boo'
        self.other_password = 'far'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", description="host description")

        # create users
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        user = User.objects.create_user(username=self.username,
                                        password=self.password)

        # create a "fs" plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = self.feedname
        pl_inst.feed.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class TaggingSerializerTests(SerializerTests):

    def setUp(self):
        super(TaggingSerializerTests, self).setUp()

        # create a tag
        self.user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag1", color="blue", owner=self.user)

        # tag self.feedname with Tag1
        feed = Feed.objects.get(name=self.feedname)
        Tagging.objects.get_or_create(tag=tag, feed=feed)

    def test_create(self):
        """
        Test whether overriden 'create' method raises a ValidationError when a new
        tagging already exists in the DB.
        """
        feed = Feed.objects.get(name=self.feedname)
        tag = Tag.objects.get(name="Tag1")
        data = {'tag': tag, 'feed': feed}
        tagging_serializer = TaggingSerializer(data=data)
        with self.assertRaises(serializers.ValidationError):
            tagging_serializer.create(data)

    def test_validate_tag(self):
        """
        Test whether custom validate_tag method returns a tag instance or
        raises a serializers.ValidationError.
        """
        feed = Feed.objects.get(name=self.feedname)
        tag = Tag.objects.get(name="Tag1")
        data = {'tag': tag, 'feed': feed}
        tagging_serializer = TaggingSerializer(data=data)
        tagging_serializer.context['request'] = mock.Mock()
        tagging_serializer.context['request'].user = self.user

        tag_inst = tagging_serializer.validate_tag(tag.id)
        self.assertEqual(tag, tag_inst)

        with self.assertRaises(serializers.ValidationError):
            tagging_serializer.validate_tag('') # error if no id is passed

        with self.assertRaises(serializers.ValidationError):
            tagging_serializer.validate_tag(tag.id + 1) # error if tag not found in DB

        with self.assertRaises(serializers.ValidationError):
            other_user = User.objects.get(username=self.other_username)
            tagging_serializer.context['request'].user = other_user
            tagging_serializer.validate_tag(tag.id) # error if users doesn't own tag

    def test_validate_feed(self):
        """
        Test whether custom validate_feed method returns a feed instance or
        raises a serializers.ValidationError.
        """
        feed = Feed.objects.get(name=self.feedname)
        tag = Tag.objects.get(name="Tag1")
        data = {'tag': tag, 'feed': feed}
        tagging_serializer = TaggingSerializer(data=data)
        tagging_serializer.context['request'] = mock.Mock()
        tagging_serializer.context['request'].user = self.user

        feed_inst = tagging_serializer.validate_feed(feed.id)
        self.assertEqual(feed, feed_inst)

        with self.assertRaises(serializers.ValidationError):
            tagging_serializer.validate_feed('')  # error if no id is passed

        with self.assertRaises(serializers.ValidationError):
            tagging_serializer.validate_feed(feed.id + 1)  # error if feed not found in DB

        with self.assertRaises(serializers.ValidationError):
            other_user = User.objects.get(username=self.other_username)
            tagging_serializer.context['request'].user = other_user
            tagging_serializer.validate_feed(feed.id)  # error if users doesn't own feed


class FeedSerializerTests(SerializerTests):

    def setUp(self):
        super(FeedSerializerTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.feed_serializer = FeedSerializer(feed)

    def test_validate_name(self):
        """
        Test whether overriden validate_name method raises a serializers.ValidationError
        when the feed name contains forward slashes or it is the special 'uploads'
        identifier.
        """
        with self.assertRaises(serializers.ValidationError):
            self.feed_serializer.validate_name('myfeed/')
        with self.assertRaises(serializers.ValidationError):
            self.feed_serializer.validate_name('uploads')
        name = self.feed_serializer.validate_name('myfeed')
        self.assertEqual(name, 'myfeed')

    def test_validate_new_owner(self):
        """
        Test whether custom validate_new_owner method returns a user instance
        or raises a serializers.ValidationError when the proposed new owner is
        not a system-registered user.
        """
        new_owner = User.objects.get(username=self.other_username)
        user_inst = self.feed_serializer.validate_new_owner(new_owner.username)
        self.assertEqual(user_inst, new_owner)

        with self.assertRaises(serializers.ValidationError):
            self.feed_serializer.validate_new_owner('not a registered user')

    def test_get_creator_username(self):
        """
        Test whether overriden get_creator_username method returns the username of the
        user that created the feed.
        """
        creator_username = self.feed_serializer.get_creator_username(self.feed_serializer.instance)
        self.assertEqual(creator_username, self.username)

    def test_get_started_jobs(self):
        """
        Test whether overriden get_started_jobs method returns the correct number of
        associated plugin instances in 'started' status.
        """
        count = self.feed_serializer.get_started_jobs(self.feed_serializer.instance)
        self.assertEqual(count, 1)

    def test_get_finished_jobs(self):
        """
        Test whether overriden get_finished_jobs method returns the correct number of
        associated plugin instances in 'finishedSuccessfully' status.
        """
        count = self.feed_serializer.get_finished_jobs(self.feed_serializer.instance)
        self.assertEqual(count, 0)

    def test_get_errored_jobs(self):
        """
        Test whether overriden get_errored_jobs method returns the correct number of
        associated plugin instances in 'finishedWithError' status.
        """
        started_jobs = self.feed_serializer.get_errored_jobs(self.feed_serializer.instance)
        self.assertEqual(started_jobs, 0)

    def test_get_cancelled_jobs(self):
        """
        Test whether overriden get_cancelled_jobs method returns the correct number of
        associated plugin instances in 'cancelled' status.
        """
        started_jobs = self.feed_serializer.get_cancelled_jobs(self.feed_serializer.instance)
        self.assertEqual(started_jobs, 0)
