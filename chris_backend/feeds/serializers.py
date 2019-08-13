
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError
from rest_framework import serializers

from plugininstances.models import STATUS_TYPES
from .models import Note, Feed, Tag, Tagging, Comment


class NoteSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)

    class Meta:
        model = Note
        fields = ('url', 'id', 'title', 'content', 'feed')


class TagSerializer(serializers.HyperlinkedModelSerializer):
    owner_username = serializers.ReadOnlyField(source='owner.username')
    feeds = serializers.HyperlinkedIdentityField(view_name='tag-feed-list')
    taggings = serializers.HyperlinkedIdentityField(view_name='tag-tagging-list')

    class Meta:
        model = Tag
        fields = ('url', 'id', 'name', 'owner_username', 'color', 'feeds', 'taggings')


class TaggingSerializer(serializers.HyperlinkedModelSerializer):
    owner_username = serializers.ReadOnlyField(source='tag.owner.username')
    tag_id = serializers.ReadOnlyField(source='tag.id')
    feed_id = serializers.ReadOnlyField(source='feed.id')
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)
    tag = serializers.HyperlinkedRelatedField(view_name='tag-detail', read_only=True)

    class Meta:
        model = Tagging
        fields = ('url', 'id', 'owner_username', 'tag_id', 'feed_id', 'tag', 'feed')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create an already existing tagging.
        """
        try:
            return super(TaggingSerializer, self).create(validated_data)
        except IntegrityError:
            feed = validated_data['feed']
            tag = validated_data['tag']
            raise serializers.ValidationError(
                {'non_field_errors':
                     ["Tagging for feed_id %s and tag_id %s already exists." %
                      (feed.id, tag.id)]})

    def validate_tag(self, tag_id):
        """
        Custom method to check that a tag id is provided, exists in the DB and
        owned by the user.
        """
        if not tag_id:
            raise serializers.ValidationError({'tag_id': ["A tag id is required."]})
        try:
            pk = int(tag_id)
            tag = Tag.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            raise serializers.ValidationError(
                {'tag_id': ["Couldn't find any tag with id %s." % tag_id]})
        user = self.context['request'].user
        if tag.owner != user:
            raise serializers.ValidationError(
                {'tag_id': ["User is not the owner of tag with tag_id %s." % tag_id]})
        return tag

    def validate_feed(self, feed_id):
        """
        Custom method to check that a feed id is provided, exists in the DB and
        owned by the user.
        """
        if not feed_id:
            raise serializers.ValidationError({'feed_id': ["A feed id is required."]})
        try:
            pk = int(feed_id)
            feed = Feed.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            raise serializers.ValidationError(
                {'feed_id': ["Couldn't find any feed with id %s." % feed_id]})
        user = self.context['request'].user
        if user not in feed.owner.all():
            raise serializers.ValidationError(
                {'feed_id': ["User is not the owner of feed with feed_id %s." % feed_id]})
        return feed


class FeedSerializer(serializers.HyperlinkedModelSerializer):
    creator_username = serializers.SerializerMethodField()
    started_jobs = serializers.SerializerMethodField()
    finished_jobs = serializers.SerializerMethodField()
    errored_jobs = serializers.SerializerMethodField()
    cancelled_jobs = serializers.SerializerMethodField()
    note = serializers.HyperlinkedRelatedField(view_name='note-detail', read_only=True)
    tags = serializers.HyperlinkedIdentityField(view_name='feed-tag-list')
    taggings = serializers.HyperlinkedIdentityField(view_name='feed-tagging-list')
    comments = serializers.HyperlinkedIdentityField(view_name='comment-list')
    files = serializers.HyperlinkedIdentityField(view_name='feedfile-list')
    plugin_instances = serializers.HyperlinkedIdentityField(
        view_name='feed-plugininstance-list')
    owner = serializers.HyperlinkedRelatedField(many=True, view_name='user-detail',
                                                read_only=True)

    class Meta:
        model = Feed
        fields = ('url', 'id', 'creation_date', 'modification_date', 'name',
                  'creator_username', 'started_jobs', 'finished_jobs', 'errored_jobs',
                  'cancelled_jobs', 'owner', 'note', 'tags', 'taggings', 'comments',
                  'files', 'plugin_instances')

    def validate_new_owner(self, username):
        """
        Custom method to check whether a new feed owner is a system-registered user.
        """
        try:
            # check if user is a system-registered user
            new_owner = User.objects.get(username=username)
        except ObjectDoesNotExist:
            raise serializers.ValidationError(
                {'owner': ["User %s is not a registered user." % username]})
        return new_owner

    def get_creator_username(self, obj):
        """
        Overriden to get the username of the creator of the feed.
        """
        return obj.get_creator().username

    def get_started_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'started' status.
        """
        if 'started' not in STATUS_TYPES:
            raise KeyError("Undefined plugin instance execution status: 'started'.")
        return obj.get_plugin_instances_status_count('started')

    def get_finished_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'finishedSuccessfully' status.
        """
        if 'finishedSuccessfully' not in STATUS_TYPES:
            raise KeyError("Undefined plugin instance execution status: "
                           "'finishedSuccessfully'.")
        return obj.get_plugin_instances_status_count('finishedSuccessfully')

    def get_errored_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'finishedWithError' status.
        """
        if 'finishedWithError' not in STATUS_TYPES:
            raise KeyError("Undefined plugin instance execution status: "
                           "'finishedWithError'.")
        return obj.get_plugin_instances_status_count('finishedWithError')

    def get_cancelled_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'cancelled' status.
        """
        if 'cancelled' not in STATUS_TYPES:
            raise KeyError("Undefined plugin instance execution status: 'cancelled'.")
        return obj.get_plugin_instances_status_count('cancelled')


class CommentSerializer(serializers.HyperlinkedModelSerializer):
    owner_username = serializers.ReadOnlyField(source='owner.username')
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)

    class Meta:
        model = Comment
        fields = ('url', 'id', 'title', 'owner_username', 'content', 'feed')
