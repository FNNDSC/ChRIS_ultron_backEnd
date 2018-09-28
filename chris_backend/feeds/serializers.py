
import os

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers

from collectionjson.fields import ItemLinkField
from collectionjson.services import collection_serializer_is_valid
from .models import Note, Tag, Feed, Comment, FeedFile


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
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail',
                                               read_only=True)

    class Meta:
        model = Tag
        fields = ('url', 'id', 'name', 'owner', 'color', 'feed')

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(TagSerializer, self).is_valid(raise_exception=raise_exception)


class FeedSerializer(serializers.HyperlinkedModelSerializer):
    note = serializers.HyperlinkedRelatedField(view_name='note-detail', read_only=True)
    tags = serializers.HyperlinkedIdentityField(view_name='tag-list')
    comments = serializers.HyperlinkedIdentityField(view_name='comment-list')
    files = serializers.HyperlinkedIdentityField(view_name='feedfile-list')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                      read_only=True)
    owner = serializers.HyperlinkedRelatedField(many=True, view_name='user-detail',
                                                read_only=True)

    class Meta:
        model = Feed
        fields = ('url', 'id', 'creation_date', 'modification_date', 'name', 'owner',
                  'note', 'tags', 'comments', 'files', 'plugin_inst')

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(FeedSerializer, self).is_valid(raise_exception=raise_exception)

    def validate_new_owner(self, username):
        """
        Custom method to check whether a new feef owner is a system-registered user.
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


class FeedFileSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail',
                                               read_only=True)
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                      read_only=True)
    file_resource = ItemLinkField('_get_file_link')
    fname = serializers.FileField(use_url=False)
    feed_id = serializers.ReadOnlyField(source='feed.id')
    plugin_inst_id = serializers.ReadOnlyField(source='plugin_inst.id')

    class Meta:
        model = FeedFile
        fields = ('url', 'id', 'fname', 'feed_id', 'plugin_inst_id', 'file_resource',
                  'feed', 'plugin_inst')

    def _get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource
        """
        fields = self.fields.items()
        # get the current url
        url_field = [v for (k, v) in fields if k == 'url'][0]
        view = url_field.view_name
        request = self.context['request']
        format = self.context['format']
        url = url_field.get_url(obj, view, request, format)
        # return url = current url + file name
        return url + os.path.basename(obj.fname.name)