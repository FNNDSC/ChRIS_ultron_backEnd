
from django.contrib.auth.models import User, Group
from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError
from rest_framework import serializers

from plugininstances.models import STATUS_CHOICES
from .models import (Note, Feed, Tag, Tagging, Comment, FeedGroupPermission,
                     FeedUserPermission)


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
    tag_id = serializers.ReadOnlyField(source='tag.id')
    feed_id = serializers.ReadOnlyField(source='feed.id')
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)
    tag = serializers.HyperlinkedRelatedField(view_name='tag-detail', read_only=True)

    class Meta:
        model = Tagging
        fields = ('url', 'id', 'tag_id', 'feed_id', 'tag', 'feed')

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
        Custom method to check that a tag id is provided and exists in the DB.
        """
        if not tag_id:
            raise serializers.ValidationError({'tag_id': ["A tag id is required."]})
        try:
            pk = int(tag_id)
            tag = Tag.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            raise serializers.ValidationError(
                {'tag_id': ["Couldn't find any tag with id %s." % tag_id]})
        return tag

    def validate_feed(self, feed_id):
        """
        Custom method to check that a feed id is provided, exists in the DB and
        the user has feed permission.
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
        if not (feed.owner == user or user.username == 'chris' or
                feed.has_user_permission(user)):
            raise serializers.ValidationError(
                {'feed_id': ["User does not have permission to tag feed with feed_id "
                             "%s." % feed_id]})
        return feed


class FeedSerializer(serializers.HyperlinkedModelSerializer):
    owner_username = serializers.ReadOnlyField(source='owner.username')
    folder_path = serializers.ReadOnlyField(source='folder.path')
    created_jobs = serializers.SerializerMethodField()
    waiting_jobs = serializers.SerializerMethodField()
    scheduled_jobs = serializers.SerializerMethodField()
    started_jobs = serializers.SerializerMethodField()
    registering_jobs = serializers.SerializerMethodField()
    finished_jobs = serializers.SerializerMethodField()
    errored_jobs = serializers.SerializerMethodField()
    cancelled_jobs = serializers.SerializerMethodField()
    folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)
    note = serializers.HyperlinkedRelatedField(view_name='note-detail', read_only=True)
    tags = serializers.HyperlinkedIdentityField(view_name='feed-tag-list')
    taggings = serializers.HyperlinkedIdentityField(view_name='feed-tagging-list')
    comments = serializers.HyperlinkedIdentityField(view_name='comment-list')
    plugin_instances = serializers.HyperlinkedIdentityField(
        view_name='feed-plugininstance-list')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = Feed
        fields = ('url', 'id', 'creation_date', 'modification_date', 'name', 'public',
                  'owner_username', 'folder_path', 'created_jobs', 'waiting_jobs',
                  'scheduled_jobs', 'started_jobs', 'registering_jobs',
                  'finished_jobs',  'errored_jobs', 'cancelled_jobs', 'folder', 'note',
                  'tags', 'taggings', 'comments', 'plugin_instances', 'owner')

    def update(self, instance, validated_data):
        """
        Overriden to grant or remove public access to the feed's folder and all its
        descendant folders, link files and files depending on the new public status of
        the feed.
        """
        if 'public' in validated_data:
            if instance.public and not validated_data['public']:
                instance.folder.remove_public_link()
                instance.folder.remove_public_access()

            elif not instance.public and validated_data['public']:
                instance.folder.grant_public_access()
                instance.folder.create_public_link()
        return super(FeedSerializer, self).update(instance, validated_data)

    def validate_name(self, name):
        """
        Overriden to check that the feed's name does not contain forward slashes.
        """
        if '/' in name:
            raise serializers.ValidationError(
                ["This field may not contain forward slashes."])
        return name

    def get_created_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'created' status.
        """
        if 'created' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: 'created'.")
        return obj.get_plugin_instances_status_count('created')

    def get_waiting_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'waiting' status.
        """
        if 'waiting' not in [status[0] for status in STATUS_CHOICES]:
            msg = "Undefined plugin instance execution status: 'waiting'."
            raise KeyError(msg)
        return obj.get_plugin_instances_status_count('waiting')

    def get_scheduled_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'scheduled' status.
        """
        if 'scheduled' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: 'scheduled'.")
        return obj.get_plugin_instances_status_count('scheduled')

    def get_started_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'started' status.
        """
        if 'started' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: 'started'.")
        return obj.get_plugin_instances_status_count('started')

    def get_registering_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'registeringFiles' status.
        """
        if 'registeringFiles' not in [status[0] for status in STATUS_CHOICES]:
            msg = "Undefined plugin instance execution status: 'registeringFiles'."
            raise KeyError(msg)
        return obj.get_plugin_instances_status_count('registeringFiles')

    def get_finished_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'finishedSuccessfully' status.
        """
        if 'finishedSuccessfully' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: "
                           "'finishedSuccessfully'.")
        return obj.get_plugin_instances_status_count('finishedSuccessfully')

    def get_errored_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'finishedWithError' status.
        """
        if 'finishedWithError' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: "
                           "'finishedWithError'.")
        return obj.get_plugin_instances_status_count('finishedWithError')

    def get_cancelled_jobs(self, obj):
        """
        Overriden to get the number of plugin instances in 'cancelled' status.
        """
        if 'cancelled' not in [status[0] for status in STATUS_CHOICES]:
            raise KeyError("Undefined plugin instance execution status: 'cancelled'.")
        return obj.get_plugin_instances_status_count('cancelled')


class FeedGroupPermissionSerializer(serializers.HyperlinkedModelSerializer):
    grp_name = serializers.CharField(write_only=True)
    feed_id = serializers.ReadOnlyField(source='feed.id')
    feed_name = serializers.ReadOnlyField(source='feed.name')
    group_id = serializers.ReadOnlyField(source='group.id')
    group_name = serializers.ReadOnlyField(source='group.name')

    class Meta:
        model = FeedGroupPermission
        fields = ('url', 'id', 'feed_id', 'feed_name', 'group_id', 'group_name',
                  'feed', 'group', 'name')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to grant access permission to a group
        that already has the permission granted. Also a link file in the SHARED folder
        pointing to the feed's folder is created if it doesn't exist.
        """
        feed = validated_data['feed']
        group = validated_data['group']

        try:
            feed_perm = super(FeedGroupPermissionSerializer, self).create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"Group '{group.name}' already has permission to access feed "
                      f"with id {feed.id}"]})

        lf = feed.folder.create_shared_link()
        lf.grant_group_permission(group, 'r')
        return feed_perm

    def validate_grp_name(self, grp_name):
        """
        Custom method to check whether the provided group name exists in the DB.
        """
        try:
            group = Group.objects.get(name=grp_name)
        except Group.DoesNotExist:
            raise serializers.ValidationError(
                {'grp_name': [f"Couldn't find any group with name '{grp_name}'."]})
        return group

class FeedUserPermissionSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(write_only=True, min_length=4, max_length=32)
    feed_id = serializers.ReadOnlyField(source='feed.id')
    feed_name = serializers.ReadOnlyField(source='feed.name')
    user_id = serializers.ReadOnlyField(source='user.id')
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = FeedUserPermission
        fields = ('url', 'id', 'feed_id', 'feed_name', 'user_id', 'user_username',
                  'feed', 'user', 'username')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to grant access permission to a user
        that already has the permission granted. Also a link file in the SHARED folder
        pointing to the feed's folder is created if it doesn't exist.
        """
        feed = validated_data['feed']
        user = validated_data['user']

        try:
            feed_perm = super(FeedUserPermissionSerializer, self).create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"User '{user.username}' already has permission to access feed "
                      f"with id {feed.id}"]})

        lf = feed.folder.create_shared_link()
        lf.grant_user_permission(user, 'r')
        return feed_perm

    def validate_username(self, username):
        """
        Custom method to check whether the provided username exists in the DB.
        """
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'username': [f"Couldn't find any user with username '{username}'."]})
        return user


class CommentSerializer(serializers.HyperlinkedModelSerializer):
    owner_username = serializers.ReadOnlyField(source='owner.username')
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)

    class Meta:
        model = Comment
        fields = ('url', 'id', 'title', 'owner_username', 'content', 'feed')
