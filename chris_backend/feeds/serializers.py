
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError

from rest_framework import serializers

from collectionjson.services import collection_serializer_is_valid
from .models import Note, Feed, Tag, Tagging, Comment


class NoteSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)

    class Meta:
        model = Note
        fields = ('url', 'id', 'title', 'content', 'feed')

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(NoteSerializer, self).is_valid(raise_exception=raise_exception)


class TagSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    feeds = serializers.HyperlinkedIdentityField(view_name='tag-feed-list')
    taggings = serializers.HyperlinkedIdentityField(view_name='tag-tagging-list')

    class Meta:
        model = Tag
        fields = ('url', 'id', 'name', 'owner', 'color', 'feeds', 'taggings')

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(TagSerializer, self).is_valid(raise_exception=raise_exception)


class TaggingSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='tag.owner.username')
    tag_id = serializers.ReadOnlyField(source='tag.id')
    feed_id = serializers.ReadOnlyField(source='feed.id')
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)
    tag = serializers.HyperlinkedRelatedField(view_name='tag-detail', read_only=True)

    class Meta:
        model = Tagging
        fields = ('url', 'id', 'owner', 'tag_id', 'feed_id', 'tag', 'feed')

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
                {'detail':
                 "Tagging for feed_id %s and tag_id %s already exists!" % (feed.id, tag.id)})

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(TaggingSerializer, self).is_valid(raise_exception=raise_exception)

    def validate_tag(self, tag_id):
        """
        Custom method to check that a tag id is provided, exists in the DB and
        owned by the user.
        """
        if not tag_id:
            raise serializers.ValidationError(
                {'detail': "A tag id is required"})
        try:
            pk = int(tag_id)
            tag = Tag.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            raise serializers.ValidationError(
                {'detail':
                 "Couldn't find any tag with id %s" % tag_id})
        user = self.context['request'].user
        if tag.owner != user:
            raise serializers.ValidationError(
                {'detail':
                 "User is not the owner of tag with tag_id %s" % tag_id})
        return tag

    def validate_feed(self, feed_id):
        """
        Custom method to check that a feed id is provided, exists in the DB and
        owned by the user.
        """
        if not feed_id:
            raise serializers.ValidationError(
                {'detail': "A feed id is required"})
        try:
            pk = int(feed_id)
            feed = Feed.objects.get(pk=pk)
        except (ValueError, ObjectDoesNotExist):
            raise serializers.ValidationError(
                {'detail':
                 "Couldn't find any feed with id %s" % feed_id})
        user = self.context['request'].user
        if user not in feed.owner.all():
            raise serializers.ValidationError(
                {'detail':
                 "User is not an owner of feed with feed_id %s" % feed_id})
        return feed


class FeedSerializer(serializers.HyperlinkedModelSerializer):
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
        fields = ('url', 'id', 'creation_date', 'modification_date', 'name', 'owner',
                  'note', 'tags', 'taggings', 'comments', 'files', 'plugin_instances')

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(FeedSerializer, self).is_valid(raise_exception=raise_exception)

    def validate_new_owner(self, username):
        """
        Custom method to check whether a new feed owner is a system-registered user.
        """
        try:
            # check if user is a system-registered user
            new_owner = User.objects.get(username=username)
        except ObjectDoesNotExist:
            raise serializers.ValidationError(
                {'detail': "%s is not a registered user" % username})
        return new_owner


class CommentSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)

    class Meta:
        model = Comment
        fields = ('url', 'id', 'title', 'owner', 'content', 'feed')

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(CommentSerializer, self).is_valid(raise_exception=raise_exception)
