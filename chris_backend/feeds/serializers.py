import os

from django.contrib.auth.models import User

from rest_framework import serializers

from collectionjson.fields import LinkField
from .models import Note, Tag, Feed, Comment, FeedFile

        
class NoteSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)

    class Meta:
        model = Note
        fields = ('url', 'title', 'content', 'feed')
        

class TagSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail',
                                               read_only=True)

    class Meta:
        model = Tag
        fields = ('url', 'name', 'owner', 'color', 'feed')
        

class FeedSerializer(serializers.HyperlinkedModelSerializer):
    note = serializers.HyperlinkedRelatedField(view_name='note-detail', read_only=True)
    tags = serializers.HyperlinkedIdentityField(view_name='tag-list')
    comments = serializers.HyperlinkedIdentityField(view_name='comment-list')
    files = serializers.HyperlinkedIdentityField(view_name='feedfile-list')
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail', read_only=True)
    owners = serializers.ListField(child=serializers.CharField(), source='owner.all',
                                   read_only=True)
    
    class Meta:
        model = Feed
        fields = ('url', 'name', 'owners', 'note', 'tags', 'comments',
                  'files', 'plugin')


class CommentSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)

    class Meta:
        model = Comment
        fields = ('url', 'title', 'owner', 'content', 'feed')


class FeedFileSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail',
                                               read_only=True)
    fname = serializers.FileField(use_url=False)
    file_resource = LinkField('_get_file_link')
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail', read_only=True)

    class Meta:
        model = FeedFile
        fields = ('url', 'fname', 'file_resource', 'feed', 'plugin')

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


class UserSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail',
                                               read_only=True)

    class Meta:
        model = User
        fields = ('url', 'username', 'feed')
