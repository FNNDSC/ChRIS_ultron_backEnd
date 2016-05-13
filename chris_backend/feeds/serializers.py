from django.contrib.auth.models import User

from rest_framework import serializers

from .models import Note, Tag, Feed, Comment
from core.renderers import LinkField


class NoteSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail', read_only=True)

    class Meta:
        model = Note
        fields = ('url', 'title', 'content', 'feed')


class TagSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail', read_only=True)

    class Meta:
        model = Tag
        fields = ('url', 'name', 'color', 'feed')        

class FeedSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    tag = serializers.HyperlinkedRelatedField(many=True, view_name='tag-detail', read_only=True)
    note = serializers.HyperlinkedRelatedField(view_name='note-detail', read_only=True)
    comment = serializers.HyperlinkedRelatedField(many=True, view_name='comment-detail', read_only=True)

    class Meta:
        model = Feed
        fields = ('url', 'owner', 'name', 'tag', 'note', 'comment')


class CommentSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail', read_only=True)

    class Meta:
        model = Comment
        fields = ('url', 'title', 'content', 'feed')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail', read_only=True)

    class Meta:
        model = User
        fields = ('url', 'username', 'feed')
        

