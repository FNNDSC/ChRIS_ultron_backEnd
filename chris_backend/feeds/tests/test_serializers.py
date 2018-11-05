from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User

from rest_framework import serializers

from plugins.models import Plugin, PluginInstance, ComputeResource
from feeds.models import Feed, Tag, Tagging
from feeds.serializers import TaggingSerializer, FeedSerializer


class SerializerTests(TestCase):

    def setUp(self):
        self.username = 'foo'
        self.password = 'bar'
        self.feedname = "Feed1"
        self.other_username = 'boo'
        self.other_password = 'far'
        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create users
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        user = User.objects.create_user(username=self.username,
                                        password=self.password)

        # create a "fs" plugin
        (plugin, tf) = Plugin.objects.get_or_create(name="pacspull", type="fs",
                                                    compute_resource=self.compute_resource)

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)
        pl_inst.feed.name = self.feedname
        pl_inst.feed.save()


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

    def test_validate_new_owner(self):
        """
        Test whether custom validate_new_owner method returns a user instance
        or raises a serializers.ValidationError when the proposed new owner is
        not a system-registered user.
        """
        feed = Feed.objects.get(name=self.feedname)
        feed_serializer = FeedSerializer(feed)
        new_owner = User.objects.get(username=self.other_username)
        user_inst = feed_serializer.validate_new_owner(new_owner.username)
        self.assertEqual(user_inst, new_owner)

        with self.assertRaises(serializers.ValidationError):
            feed_serializer.validate_new_owner('not a registered user')
